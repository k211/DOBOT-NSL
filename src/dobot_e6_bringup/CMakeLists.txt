cmake_minimum_required(VERSION 3.8)
project(dobot_e6_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config rviz robots models
  DESTINATION share/${PROJECT_NAME}
)

# Scripts must stay executable — a non-executable installed script makes
# ros2 launch tear down every started action (handoff §11.8).
install(PROGRAMS
  scripts/home_arm.py
  scripts/activate_servo.py
  scripts/joy_to_servo.py
  scripts/haptic_feedback.py
  scripts/ft_relay.py
  scripts/green_box_marker.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
