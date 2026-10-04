cmake_minimum_required(VERSION 3.8)
project(dobot_e6_hw)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

# dobot_api.py is a module, not a node, but installing it into lib/ next to
# the node keeps `from dobot_api import ...` working without a setup.py.
install(PROGRAMS
  scripts/dobot_tcp_node.py
  scripts/dobot_api.py
  scripts/go_home.py
  scripts/home_pose.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
