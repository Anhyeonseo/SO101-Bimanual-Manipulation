"""ROS 2 readback bridge with opt-in, one-point motion commands."""

from __future__ import annotations

from pathlib import Path
import sys
import time

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from trajectory_msgs.msg import JointTrajectory

from .calibration import load_calibration
from .device_discovery import resolve_serial_device
from .transport import ActuatorTransport, TransportError


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

        serial_device = resolve_serial_device(
            str(self.get_parameter("serial_device").value)
        )
        baud_rate = self.get_parameter("baud_rate").value
        feedback_rate = self.get_parameter("feedback_rate_hz").value
        self._allow_motion = bool(self.get_parameter("allow_motion").value)
        calibration_file = self.get_parameter("calibration_file").value

        if not 1.0 <= feedback_rate <= 10.0:
            raise ValueError("feedback_rate_hz must be within 1..10")

        self._calibration = load_calibration(calibration_file)
        self._faulted = False
        self._consecutive_errors = 0
        self._feedback_resume_at = 0.0
        self._motion_armed = False

        try:
            import serial

            self._serial = serial.Serial(
                serial_device,
                baud_rate,
                timeout=0.12,
                write_timeout=0.12,
            )
            self._transport = ActuatorTransport(
                self._serial,
                response_timeout_s=0.12,
            )
            hello = self._transport.enter_binary_mode()
        except Exception as error:
            raise RuntimeError(f"STM32 connection failed: {error}") from error

        if hello.calibration_hash != self._calibration.calibration_hash:
            self._serial.close()
            raise RuntimeError(
                "calibration hash mismatch: "
                f"MCU=0x{hello.calibration_hash:08X}, "
                f"host=0x{self._calibration.calibration_hash:08X}"
            )

        if self._allow_motion:
            if hello.stop_latched:
                self.get_logger().warning(
                    "STM32 stop is latched; inspect the arm and call /clear_fault"
                )
            else:
                self._transport.arm_and_enable(self._calibration.calibration_hash)
                self._motion_armed = True

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
            message = JointState()
            message.header.stamp = self.get_clock().now().to_msg()
            message.name = self._calibration.ros_joint_names
            message.position = self._calibration.raw_feedback_to_radians(
                state.raw_positions
            )
            self._joint_publisher.publish(message)
            self._process_motion_results()
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
            self._transport.clear_fault()
            if self._allow_motion:
                self._transport.arm_and_enable(self._calibration.calibration_hash)
                self._motion_armed = True
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
        try:
            self._transport.safe_stop()
        except Exception as stop_error:
            self.get_logger().error(f"SAFE_STOP acknowledgement failed: {stop_error}")

    def destroy_node(self) -> bool:
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
        if hasattr(self, "_serial") and self._serial.is_open:
            self._serial.close()
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = SingleArmBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
