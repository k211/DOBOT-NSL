#!/usr/bin/env bash
# Source this file from any directory to activate ROS, the project Python
# environment, and this colcon workspace.  COLCON_CURRENT_PREFIX works around
# the generic colcon setup.sh generator not quoting workspace paths with spaces.

_dobot_workspace="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${ROS_DISTRO:-}" ]]; then
  source /opt/ros/humble/setup.bash
elif [[ "$ROS_DISTRO" != "humble" ]]; then
  echo "setup_dobot.bash: expected ROS 2 Humble, found $ROS_DISTRO" >&2
  unset _dobot_workspace
  return 1
fi

if [[ ! -f "$_dobot_workspace/.venv/bin/activate" ]]; then
  echo "setup_dobot.bash: .venv is missing; follow the dependency setup in README.md" >&2
  unset _dobot_workspace
  return 1
fi
source "$_dobot_workspace/.venv/bin/activate"

if [[ ! -f "$_dobot_workspace/install/local_setup.sh" ]]; then
  echo "setup_dobot.bash: install/local_setup.sh is missing; run colcon build" >&2
  unset _dobot_workspace
  return 1
fi

# Resource retriever and Gazebo Fortress cannot parse file URLs whose paths
# contain spaces. Present the install prefixes through a stable no-space alias;
# all links are recreated when this setup file is sourced (including after a
# reboot clears /tmp).
_dobot_overlay="/tmp/dobot_e6_overlay_$(id -u)"
mkdir -p "$_dobot_overlay"
ln -sfn "$_dobot_workspace/install/_local_setup_util_sh.py" \
  "$_dobot_overlay/_local_setup_util_sh.py"
for _dobot_package in dobot_e6_description dobot_e6_bringup dobot_e6_hw; do
  ln -sfn "$_dobot_workspace/install/$_dobot_package" \
    "$_dobot_overlay/$_dobot_package"
done

COLCON_CURRENT_PREFIX="$_dobot_overlay" \
  source "$_dobot_workspace/install/local_setup.sh"
export IGN_GAZEBO_RESOURCE_PATH="$_dobot_overlay/dobot_e6_description/share${IGN_GAZEBO_RESOURCE_PATH:+:$IGN_GAZEBO_RESOURCE_PATH}"

unset _dobot_package
unset _dobot_overlay
unset _dobot_workspace
