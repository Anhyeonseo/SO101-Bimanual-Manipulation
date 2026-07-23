from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _include(package_name, launch_file):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare(package_name), "launch", launch_file]
            )
        )
    )


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="so101_isaac_bridge",
                executable="bridge_node",
                name="so101_isaac_bridge",
                output="screen",
            ),
            _include("so101_moveit_config", "rsp.launch.py"),
            _include(
                "so101_moveit_config",
                "static_virtual_joint_tfs.launch.py",
            ),
            _include("so101_moveit_config", "move_group.launch.py"),
            _include("so101_moveit_config", "moveit_rviz.launch.py"),
        ]
    )
