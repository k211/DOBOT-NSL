cmake_minimum_required(VERSION 3.8)
project(dobot_e6_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY urdf meshes srdf config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
