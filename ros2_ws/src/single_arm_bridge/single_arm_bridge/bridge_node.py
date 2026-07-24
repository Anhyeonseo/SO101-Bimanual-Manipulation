"""ROS 2 readback bridge with opt-in, one-point motion commands."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from ament_index_python.packages import get_package_share_directory

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from sensor_msgs.msg import JointState

from std_srvs.srv import Trigger

from trajectory_msgs.msg import JointTrajectory

from .action_execution import MotionExecutionCore
from .backend_lease import acquire_backend_lease
from .calibration import load_calibration
from .device_discovery import resolve_serial_device
from .follow_joint_trajectory_server import FollowJointTrajectoryActionAdapter
from .hardware_identity import validate_hardware_identity
from .motion_goal_arbiter import MotionGoalArbiter
from .parallel_gripper_command_server import (
    ParallelGripperCommandActionAdapter,
)
from .serial_port import open_exclusive_serial
from .transport import (
    ActuatorTransport,
    StateResponseDeferred,
    TransportError,
)


DEFAULT_DEVICE = "auto"


class SingleArmBridge(Node):
    def __init__(self) -> None:
        super().__init__("single_arm_bridge")
        default_calibration = str(
            Path(get_package_share_directory("single_arm_bridge"))
            / "config"
            / "single_arm_calibration.json"
        )
        self.declare_parameter("serial_device", DEFAULT_DEVICE)
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("feedback_rate_hz", 5.0)
        self.declare_parameter("allow_motion", False)
        self.declare_parameter("calibration_file", default_calibration)

        baud_rate = self.get_parameter("baud_rate").value
        feedback_rate = self.get_parameter("feedback_rate_hz").value
        self._allow_motion = bool(self.get_parameter("allow_motion").value)
        calibration_file = self.get_parameter("calibration_file").value

        if not 1.0 <= feedback_rate <= 10.0:
            raise ValueError("feedback_rate_hz must be within 1..10")

        self._faulted = False
        self._consecutive_errors = 0
        self._feedback_resume_at = 0.0
        self._motion_armed = False
        self._serial = None
        self._backend_lease = None
        self._arm_action_adapter = None
        self._gripper_action_adapter = None
        self._motion_arbiter = MotionGoalArbiter()
        self._latest_positions: tuple[float, ...] | None = None
        self._latest_feedback_at = 0.0
        self._feedback_max_age_s = max(0.5, 2.5 / feedback_rate)

        try:
            ros_domain_id = int(os.environ.get("ROS_DOMAIN_ID", "0"))
            self._backend_lease = acquire_backend_lease("stm32", ros_domain_id)
            serial_device = resolve_serial_device(
                str(self.get_parameter("serial_device").value)
            )
            self._calibration = load_calibration(calibration_file)

            import serial

            self._serial = open_exclusive_serial(
                serial,
                serial_device,
                baud_rate,
                timeout_s=0.12,
            )
            self._transport = ActuatorTransport(
                self._serial,
                response_timeout_s=0.12,
            )
            hello = self._transport.enter_binary_mode()
            validate_hardware_identity(
                hello,
                self._calibration.calibration_hash,
            )
            self._execution_core = MotionExecutionCore(
                self._transport,
                hello,
                self._calibration,
            )
        except Exception as error:
            if self._serial is not None and self._serial.is_open:
                self._serial.close()
            if self._backend_lease is not None:
                self._backend_lease.release()
            raise RuntimeError(f"STM32 connection failed: {error}") from error

        self._joint_publisher = self.create_publisher(
            JointState,
            "joint_states",
            10,
        )
        self._command_subscription = self.create_subscription(
            JointTrajectory,
            "joint_command",
            self._on_joint_command,
            10,
        )
        self._clear_fault_service = self.create_service(
            Trigger,
            "clear_fault",
            self._on_clear_fault,
        )
        self._heartbeat_timer = self.create_timer(0.1, self._send_heartbeat)
        self._feedback_timer = self.create_timer(
            1.0 / feedback_rate,
            self._publish_feedback,
        )
        arm_attempted = False
        try:
            if self._allow_motion:
                self._arm_action_adapter = FollowJointTrajectoryActionAdapter(
                    self,
                    self._execution_core,
                    self._calibration,
                    self._motion_backend_ready,
                    self._fresh_joint_positions,
                    motion_arbiter=self._motion_arbiter,
                )
                self._gripper_action_adapter = (
                    ParallelGripperCommandActionAdapter(
                        self,
                        self._execution_core,
                        self._calibration,
                        self._motion_backend_ready,
                        self._fresh_joint_positions,
                        motion_arbiter=self._motion_arbiter,
                    )
                )
                if hello.stop_latched:
                    self.get_logger().warning(
                        "STM32 stop is latched; inspect the arm and call "
                        "/clear_fault"
                    )
                else:
                    arm_attempted = True
                    self._transport.arm_and_enable(
                        self._calibration.calibration_hash
                    )
                    self._motion_armed = True
        except Exception as error:
            if arm_attempted:
                try:
                    self._transport.safe_stop()
                except Exception:
                    pass
            if self._arm_action_adapter is not None:
                self._arm_action_adapter.destroy()
                self._arm_action_adapter = None
            if self._gripper_action_adapter is not None:
                self._gripper_action_adapter.destroy()
                self._gripper_action_adapter = None
            if self._serial is not None and self._serial.is_open:
                self._serial.close()
            if self._backend_lease is not None:
                self._backend_lease.release()
            raise RuntimeError(
                f"STM32 motion initialization failed: {error}"
            ) from error

        if self._motion_armed:
            mode = "MOTION_ENABLED"
        elif self._allow_motion:
            mode = "MOTION_BLOCKED_LATCHED"
        else:
            mode = "READ_ONLY"
        self.get_logger().info(
            f"connected firmware=0x{hello.firmware_version:08X} "
            f"calibration=0x{hello.calibration_hash:08X} mode={mode}"
        )

    def _send_heartbeat(self) -> None:
        if self._faulted:
            return
        try:
            self._transport.heartbeat()
        except Exception as error:
            self._handle_transport_error("heartbeat", error)

    def _publish_feedback(self) -> None:
        if self._faulted:
            return
        if time.monotonic() < self._feedback_resume_at:
            return
        if self._execution_core.active:
            # Firmware trajectory execution owns the servo bus. The Action
            # polling thread collects its unsolicited terminal status; resume
            # physical position reads on the first regular cycle after it ends.
            self._consecutive_errors = 0
            return
        try:
            state = self._transport.get_state(include_positions=True)
            if state.stop_latched:
                self._handle_transport_error(
                    "safety latch",
                    TransportError("STM32 stop is latched"),
                    immediate=True,
                )
                return
            assert state.raw_positions is not None
            positions = tuple(
                self._calibration.raw_feedback_to_radians(state.raw_positions)
            )
            self._latest_positions = positions
            self._latest_feedback_at = time.monotonic()
            message = JointState()
            message.header.stamp = self.get_clock().now().to_msg()
            message.name = self._calibration.ros_joint_names
            message.position = list(positions)
            self._joint_publisher.publish(message)
            if (
                self._arm_action_adapter is None
                and self._gripper_action_adapter is None
            ):
                self._process_motion_results()
            self._consecutive_errors = 0
        except StateResponseDeferred:
            # A terminal motion result is valid serial traffic. The MCU can omit
            # the overlapping position response while final verification ends;
            # the next regular 5 Hz cycle will obtain fresh joint state.
            self._consecutive_errors = 0
        except Exception as error:
            self._handle_transport_error("feedback", error)

    def _process_motion_results(self) -> None:
        for result in self._transport.drain_motion_results():
            if result.status_code == 6:
                self.get_logger().info(
                    "motion completed "
                    f"max_error_raw={result.detail} sequence={result.request_sequence}"
                )
                continue
            self._handle_transport_error(
                "motion result",
                TransportError(
                    f"status={result.status_code} detail={result.detail} "
                    f"sequence={result.request_sequence}"
                ),
                immediate=True,
            )

    def _on_joint_command(self, message: JointTrajectory) -> None:
        if (
            self._arm_action_adapter is not None
            or self._gripper_action_adapter is not None
        ):
            self.get_logger().error(
                "joint command rejected: standard Actions own motion"
            )
            return
        if not self._allow_motion or self._faulted or not self._motion_armed:
            self.get_logger().error("joint command rejected: motion is not enabled")
            return
        if len(message.points) != 1:
            self.get_logger().error("joint command requires exactly one point")
            return
        expected_names = self._calibration.ros_joint_names
        if set(message.joint_names) != set(expected_names):
            self.get_logger().error("joint command must contain all six known joints")
            return

        point = message.points[0]
        if len(point.positions) != 6:
            self.get_logger().error("joint command must contain six positions")
            return
        duration_ms = (
            point.time_from_start.sec * 1000
            + point.time_from_start.nanosec // 1_000_000
        )
        indexed = dict(zip(message.joint_names, point.positions, strict=True))
        ordered_positions = [indexed[name] for name in expected_names]

        try:
            positions_urad = self._calibration.radians_to_urad(ordered_positions)
            self._transport.send_setpoint(positions_urad, duration_ms)
            self._feedback_resume_at = (
                time.monotonic() + (duration_ms / 1000.0) + 0.3
            )
            self.get_logger().info(f"joint command accepted duration={duration_ms}ms")
        except Exception as error:
            self._handle_transport_error("joint command", error, immediate=True)

    def _on_clear_fault(self, request: Trigger.Request, response: Trigger.Response):
        del request
        try:
            if self._execution_core.active or self._motion_arbiter.owner is not None:
                raise RuntimeError("cannot clear fault while an Action goal is active")
            self._transport.clear_fault()
            hello = self._transport.enter_binary_mode()
            validate_hardware_identity(
                hello,
                self._calibration.calibration_hash,
            )
            if self._allow_motion:
                self._transport.arm_and_enable(self._calibration.calibration_hash)
                self._motion_armed = True
            self._execution_core.replace_transport_after_explicit_recovery(
                self._transport,
                hello,
            )
            self._faulted = False
            self._consecutive_errors = 0
            response.success = True
            response.message = (
                "fault cleared; commands enabled"
                if self._allow_motion
                else "fault cleared; read-only mode"
            )
            self.get_logger().info(response.message)
        except Exception as error:
            self._motion_armed = False
            self._faulted = True
            try:
                self._transport.safe_stop()
            except Exception:
                pass
            response.success = False
            response.message = f"fault clear rejected: {error}"
            self.get_logger().error(response.message)
        return response

    def _handle_transport_error(
        self,
        stage: str,
        error: Exception,
        immediate: bool = False,
    ) -> None:
        self._consecutive_errors += 1
        if not immediate and self._consecutive_errors < 3:
            self.get_logger().warning(
                f"transient {stage} delay "
                f"({self._consecutive_errors}/3): {error}"
            )
            return
        self.get_logger().error(f"{stage} error: {error}")
        self._faulted = True
        self._motion_armed = False
        if self._arm_action_adapter is not None:
            self._arm_action_adapter.notify_connection_loss(
                f"{stage}: {error}"
            )
        if self._gripper_action_adapter is not None:
            self._gripper_action_adapter.notify_connection_loss(
                f"{stage}: {error}"
            )
        try:
            self._transport.safe_stop()
        except Exception as stop_error:
            self.get_logger().error(f"SAFE_STOP acknowledgement failed: {stop_error}")

    def destroy_node(self) -> bool:
        self.prepare_shutdown()
        if self._arm_action_adapter is not None:
            self._arm_action_adapter.destroy()
            self._arm_action_adapter = None
        if self._gripper_action_adapter is not None:
            self._gripper_action_adapter.destroy()
            self._gripper_action_adapter = None
        if (
            hasattr(self, "_transport")
            and self._allow_motion
            and self._motion_armed
            and not self._faulted
        ):
            disable_error: Exception | None = None
            for _ in range(3):
                try:
                    # Ctrl+C may interrupt a feedback read after consuming only
                    # part of a frame. Drop that fragment, refresh the firmware
                    # watchdog, and retry the idempotent DISABLE transaction.
                    self._serial.reset_input_buffer()
                    self._transport.heartbeat()
                    self._transport.disable()
                    self._motion_armed = False
                    disable_error = None
                    break
                except Exception as error:
                    disable_error = error
            if disable_error is not None:
                message = f"DISABLE during shutdown failed: {disable_error}"
                if rclpy.ok():
                    self.get_logger().error(message)
                else:
                    print(message, file=sys.stderr)
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        if self._backend_lease is not None:
            self._backend_lease.release()
        return super().destroy_node()

    def _motion_backend_ready(self) -> bool:
        return (
            self._allow_motion
            and self._motion_armed
            and not self._faulted
            and not self._execution_core.blocked
        )

    def _fresh_joint_positions(self) -> tuple[float, ...] | None:
        positions = self._latest_positions
        if positions is None:
            return None
        if time.monotonic() - self._latest_feedback_at > self._feedback_max_age_s:
            return None
        return positions

    def prepare_shutdown(self) -> None:
        if self._arm_action_adapter is not None:
            self._arm_action_adapter.notify_connection_loss("node shutdown")
        if self._gripper_action_adapter is not None:
            self._gripper_action_adapter.notify_connection_loss("node shutdown")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = SingleArmBridge()
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.prepare_shutdown()
        if executor is not None:
            executor.shutdown(timeout_sec=2.0)
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
