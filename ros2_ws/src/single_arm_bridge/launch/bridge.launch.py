from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
import os


def generate_launch_description():
    share = get_package_share_directory("single_arm_bridge")
    config_directory = os.path.join(share, "config")
    parameter_files = [os.path.join(config_directory, "bridge.yaml")]
    local_config = os.path.join(config_directory, "bridge.local.yaml")
    if os.path.isfile(local_config):
        parameter_files.append(local_config)
    return LaunchDescription(
        [
            Node(
                package="single_arm_bridge",
                executable="bridge_node",
                name="single_arm_bridge",
                output="screen",
                parameters=parameter_files,
            )
        ]
    )
