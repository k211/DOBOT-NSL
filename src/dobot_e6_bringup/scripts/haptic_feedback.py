#!/usr/bin/python3
"""
Graduated haptic feedback driven by the Jacobian condition number.

Intensity curve (power law, EXPO_POWER=1.5):
  cond_smooth < LOWER_THRESHOLD        → 0.0
  cond_smooth between LOWER and STOP   → t ^ EXPO_POWER  (t normalised 0‥1)
  cond_smooth > HARDSTOP_THRESHOLD     → 1.0

Servo status overrides:
  DECELERATE_FOR_APPROACHING_SINGULARITY → intensity floored at DECEL_INTENSITY
  HALT_FOR_SINGULARITY / HALT_FOR_COLLISION → intensity = 1.0 (hard override)

Non-finite condition number (true singularity at sv[-1] ≈ 0):
  cond_smooth is driven to hardstop × 3 so the graduated curve also reaches 1.0
  independently of the HALT override (which may arrive one tick late).

Recovery debounce:
  After a HALT, once servo reports NO_WARNING for RECOVERY_DEBOUNCE seconds all
  latched state (_active, _cond_smooth) is cleared, guaranteeing silence even if
  the EMA hasn't fully decayed.

Joint-limit proximity (ARM_JOINTS only — gripper excluded):
  Limits parsed from URDF (revolute joints only; continuous joints skipped).
  Within JOINT_MARGIN radians of a limit → ramp via _curve(), combined with
  singularity intensity via max().

Single active flag:
  Rumble starts when combined intensity > ACTIVE_ENTER, stops below ACTIVE_EXIT.
  Both the motor and the log are gated on the same flag — they cannot diverge.
  A perceptible floor (INTENSITY_FLOOR) is applied whenever active.

Auto-calibration, Pinocchio Jacobian, and continuous-joint cos/sin handling
are unchanged from the previous revision.

TUNING: watch 'cond_i= / joint_i= / intensity= / active=' in the log.
  If home buzzes after calibration, raise CALIBRATION_MARGIN (e.g. 1.5 → 2.0).
"""

import math
import xml.etree.ElementTree as ET

import numpy as np
import pinocchio as pin

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from geometry_msgs.msg import WrenchStamped
from moveit_msgs.msg import ServoStatus

import evdev
from evdev import ecodes, ff

# ── tunable constants ──────────────────────────────────────────────────────────
LOWER_THRESHOLD    = 0.0    # 0 = auto-calibrate; >0 = fixed value
HARDSTOP_THRESHOLD = 0.0    # 0 = auto-set to LOWER × HARDSTOP_MULT

EXPO_POWER         = 1.5    # curve shape: 1=linear, 2=quadratic; 1.5 perceptible early
DECEL_INTENSITY    = 0.55   # minimum intensity when servo signals DECEL_FOR_APPROACHING
INTENSITY_FLOOR    = 0.25   # minimum felt magnitude while active (perceptibility floor)

CALIBRATION_WINDOW = 25.0   # seconds of NO_WARNING data to collect
CALIBRATION_MARGIN = 1.5    # LOWER = peak_cond_in_window × margin
HARDSTOP_MULT      = 1.8    # HARDSTOP = LOWER × multiplier

ACTIVE_ENTER       = 0.05   # start rumble when intensity rises above this
ACTIVE_EXIT        = 0.02   # stop rumble when intensity falls below this
EMA_ALPHA          = 0.35   # condition-number EMA weight (higher → more responsive)

RECOVERY_DEBOUNCE  = 1.5    # seconds of NO_WARNING after a HALT before forcing silence

JOINT_MARGIN       = 0.15   # rad — graduated rumble starts within this of each limit

# Contact-force rumble (independent of the singularity/joint machinery).
# Uses the force-vector magnitude from /ft_sensor/wrench, so a push along any
# axis triggers it.
# ME6 SIM SCALING: position-controlled joints vs the static box behave ~25 N/mm
# stiff — measured ramp 0.5 → 600 N over ~1 s of pressing (probe weight alone
# reads ~0.49 N at rest). Hence a much wider band than the Kinova's 2/8 N.
# ponytail: sim-only tuning. On real hardware with an external wrist F/T sensor
# revert to FORCE_THRESHOLD≈2, FORCE_MAX≈8 (handoff §0.5/§12), or soften the
# contact in SDF if graded sim forces in true newtons ever matter.
FORCE_THRESHOLD    = 5.0    # N — below this, no force rumble (clears 0.49 N baseline)
FORCE_MAX          = 400.0  # N — at/above this, full-strength force rumble
FORCE_FLOOR        = 0.30   # min intensity the instant force crosses the threshold

ARM_JOINTS             = [f'joint{i}' for i in range(1, 7)]  # ME6: joint1..joint6
EE_FRAME_CANDIDATES    = ['Link6', 'us_probe_link']  # ME6 flange, then probe
INTENSITY_DEADBAND     = 0.04
EFFECT_DURATION_MS     = 300    # effect length; refreshed every 100 ms → continuous
LOG_INTERVAL           = 3.0
# ──────────────────────────────────────────────────────────────────────────────


def _curve(t: float) -> float:
    """Map t ∈ [0,1] through the chosen power curve."""
    return float(np.clip(t, 0.0, 1.0) ** EXPO_POWER)


class HapticFeedback(Node):
    def __init__(self):
        super().__init__('haptic_feedback')

        self._model        = None
        self._data         = None
        self._ee_frame_id  = -1
        # name -> (idx_q, nq, idx_v) for every joint in the model
        self._joint_info:   dict[str, tuple[int, int, int]] = {}
        # [(name, idx_q, nq, idx_v)] for the 7 arm joints, in kinematic order
        self._arm_info:     list[tuple[str, int, int, int]] = []
        # idx_v column indices for the 6×7 arm sub-Jacobian
        self._arm_v_cols:   list[int] = []
        # (lower, upper) limits for revolute joints only, parsed from URDF
        self._joint_limits: dict[str, tuple[float, float]] = {}

        self._cond           = 0.0
        self._cond_smooth    = 0.0
        self._servo_code     = ServoStatus.NO_WARNING
        self._cond_intensity  = 0.0   # stored for logging
        self._joint_intensity = 0.0   # stored for logging
        self._intensity      = 0.0
        # Force-contact intensity — updated by /ft_sensor/wrench, combined in
        # _tick() so it works even before singularity calibration finishes.
        self._force_mag       = 0.0
        self._force_intensity = 0.0
        self._last_sent      = 0.0
        self._log_t          = 0.0
        # Single gate for both motor output and log — replaces the old _buzzing flag
        # which diverged from _intensity when joint_intensity kept the motor running
        # while _buzzing had already flipped False.
        self._active         = False
        # HALT recovery tracking
        self._in_halt        = False
        self._recovery_t     = None
        self._diag_done      = False

        self._lower    = LOWER_THRESHOLD    if LOWER_THRESHOLD    > 0.0 else None
        self._hardstop = HARDSTOP_THRESHOLD if HARDSTOP_THRESHOLD > 0.0 else None
        self._cal_done = self._lower is not None
        self._cal_conds: list[float] = []
        self._cal_start = None

        self._device = None
        self._eff_id = -1

        self._open_device()

        qos = QoSProfile(depth=1)
        qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self.create_subscription(String,      '/robot_description', self._urdf_cb,  qos)
        self.create_subscription(ServoStatus, '/servo_node/status', self._servo_cb, 10)
        self.create_subscription(JointState,  '/joint_states',      self._joint_cb, 10)
        self.create_subscription(WrenchStamped, '/ft_sensor/wrench', self._ft_cb,   10)
        self.create_timer(0.1, self._tick)

    # ── evdev ─────────────────────────────────────────────────────────────────

    def _open_device(self):
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if ('DualSense' in dev.name or 'Sony Interactive' in dev.name) \
                    and ecodes.EV_FF in dev.capabilities():
                self._device = dev
                self.get_logger().info(f'Haptic device: {dev.name}  ({dev.path})')
                self._eff_id = self._upload_effect(0.0)
                return
        self.get_logger().error('DualSense FF device not found — haptics disabled.')

    def _upload_effect(self, intensity: float) -> int:
        magnitude = int(max(0.0, min(1.0, intensity)) * 0xFFFF)
        effect = ff.Effect(
            ecodes.FF_RUMBLE, self._eff_id, 0,
            ff.Trigger(0, 0),
            ff.Replay(EFFECT_DURATION_MS, 0),
            ff.EffectType(ff_rumble_effect=ff.Rumble(
                strong_magnitude=magnitude, weak_magnitude=0)),
        )
        return self._device.upload_effect(effect)

    def _stop_rumble(self):
        """Authoritatively stop rumble: stop playback, erase the effect slot,
        then upload a fresh silent slot so no stale playing state survives in
        the driver (some drivers ignore a stop-write on a looping effect)."""
        if self._device and self._eff_id >= 0:
            try:
                self._device.write(ecodes.EV_FF, self._eff_id, 0)   # stop playback
                self._device.erase_effect(self._eff_id)              # purge from driver
            except OSError:
                pass
            self._eff_id = -1                          # invalidate before fresh upload
            try:
                self._eff_id = self._upload_effect(0.0)
            except OSError:
                pass
        self._last_sent = 0.0

    def destroy_node(self):
        """Silence the controller before the node tears down."""
        self._stop_rumble()
        super().destroy_node()

    # ── robot model ───────────────────────────────────────────────────────────

    def _urdf_cb(self, msg: String):
        model = pin.buildModelFromXML(msg.data)

        # Build per-joint info: (idx_q, nq, idx_v).
        # Continuous joints (1/3/5/7 on Gen3) have nq=2 (cos,sin) and nv=1,
        # so idx_q != idx_v after the first continuous joint.
        joint_info: dict[str, tuple[int, int, int]] = {}
        arm_info:   list[tuple[str, int, int, int]] = []
        arm_v_cols: list[int] = []
        for jid in range(1, model.njoints):
            name = model.names[jid]
            j    = model.joints[jid]
            joint_info[name] = (j.idx_q, j.nq, j.idx_v)
            if name in ARM_JOINTS:
                arm_info.append((name, j.idx_q, j.nq, j.idx_v))
                arm_v_cols.append(j.idx_v)

        # Parse revolute joint limits from URDF XML.
        # Continuous joints carry no <limit> element and are correctly skipped.
        joint_limits: dict[str, tuple[float, float]] = {}
        try:
            root = ET.fromstring(msg.data)
            for jelem in root.findall('joint'):
                if jelem.get('type') == 'revolute':
                    jname = jelem.get('name', '')
                    lim   = jelem.find('limit')
                    if lim is not None:
                        joint_limits[jname] = (
                            float(lim.get('lower', 0.0)),
                            float(lim.get('upper', 0.0)),
                        )
        except ET.ParseError as exc:
            self.get_logger().error(f'URDF XML parse error: {exc}')

        frame_names = {f.name for f in model.frames}
        ee_id = -1
        for cand in EE_FRAME_CANDIDATES:
            if cand in frame_names:
                ee_id = model.getFrameId(cand)
                self.get_logger().info(f'EE frame: {cand}')
                break
        if ee_id < 0:
            ee_id = len(model.frames) - 1
            self.get_logger().warn(f'EE frame not found — using: {model.frames[ee_id].name}')

        self._model        = model
        self._data         = model.createData()
        self._ee_frame_id  = ee_id
        self._joint_info   = joint_info
        self._arm_info     = arm_info
        self._arm_v_cols   = arm_v_cols
        self._joint_limits = joint_limits
        self._diag_done    = False   # re-run diagnostic if URDF is republished

        arm_lim_str = ', '.join(
            f'{n}:[{lo:.2f},{hi:.2f}]'
            for n, (lo, hi) in joint_limits.items() if n in ARM_JOINTS)
        cal_str = (f'fixed LOWER={self._lower:.1f}' if self._cal_done
                   else f'auto-calibrating ({CALIBRATION_WINDOW:.0f} s)')
        self.get_logger().info(
            f'Model loaded — {len(arm_v_cols)} arm DOF  '
            f'revolute limits=[{arm_lim_str}]  threshold={cal_str}')

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _servo_cb(self, msg: ServoStatus):
        self._servo_code = msg.code

    def _ft_cb(self, msg: WrenchStamped):
        # Magnitude of the contact force; ramp from FORCE_THRESHOLD..FORCE_MAX.
        # Kept separate from self._intensity and folded in at _tick() so contact
        # rumble fires regardless of singularity calibration state.
        f = msg.wrench.force
        self._force_mag = math.sqrt(f.x * f.x + f.y * f.y + f.z * f.z)
        if self._force_mag > FORCE_THRESHOLD:
            ramp = _curve((self._force_mag - FORCE_THRESHOLD) / (FORCE_MAX - FORCE_THRESHOLD))
            self._force_intensity = max(FORCE_FLOOR, ramp)
        else:
            self._force_intensity = 0.0

    def _joint_cb(self, js: JointState):
        if self._model is None or not self._arm_v_cols:
            return

        pos_map: dict[str, float] = dict(zip(js.name, js.position))

        # ── startup diagnostic ─────────────────────────────────────────────
        if not self._diag_done:
            self._diag_done = True
            self.get_logger().info(f'Arm idx_v cols: {self._arm_v_cols}')
            for name, idx_q, nq, idx_v in self._arm_info:
                pos  = pos_map.get(name, float('nan'))
                lim  = self._joint_limits.get(name)
                base = (f'{name}: pos={pos:.3f}  '
                        f'idx_q={idx_q} nq={nq} idx_v={idx_v}')
                if lim:
                    lo, hi    = lim
                    clearance = min(pos - lo, hi - pos)
                    detail    = (f'  clearance={clearance:.3f} rad'
                                 f'  limit=[{lo:.2f}, {hi:.2f}]')
                    if clearance < JOINT_MARGIN:
                        self.get_logger().warning(
                            base + detail +
                            f'  ← < JOINT_MARGIN={JOINT_MARGIN} rad — '
                            'Home pose is inside the limit margin; '
                            'lower JOINT_MARGIN or use a home pose with more clearance')
                    else:
                        self.get_logger().info(base + detail)
                else:
                    self.get_logger().info(base + '  (continuous — no limit)')

        # ── build configuration vector q ───────────────────────────────────
        # Continuous joints (nq==2) store (cos θ, sin θ), not θ directly.
        q = pin.neutral(self._model)
        for name, (idx_q, nq, _) in self._joint_info.items():
            pos = pos_map.get(name)
            if pos is None:
                continue
            if nq == 1:
                q[idx_q] = pos
            else:   # nq == 2: continuous joint
                q[idx_q]     = math.cos(pos)
                q[idx_q + 1] = math.sin(pos)

        # ── Jacobian condition number ───────────────────────────────────────
        # getFrameJacobian returns a 6×model.nv matrix indexed by idx_v.
        # arm_v_cols selects the 7 arm columns correctly even when continuous
        # joints have shifted idx_v away from idx_q.
        pin.computeJointJacobians(self._model, self._data, q)
        pin.updateFramePlacements(self._model, self._data)
        J = pin.getFrameJacobian(self._model, self._data, self._ee_frame_id,
                                  pin.ReferenceFrame.LOCAL_WORLD_ALIGNED)
        J_arm = J[:, self._arm_v_cols]   # 6 × 7, velocity-indexed
        # Alternative metrics (leave default cond-number behaviour unchanged):
        #   sv_min = sv[-1]   # smallest singular value → 0 at singularity
        #   manip  = np.sqrt(max(0.0, np.linalg.det(J_arm @ J_arm.T)))  # Yoshikawa
        _, sv, _ = np.linalg.svd(J_arm, full_matrices=False)
        raw_cond = float(sv[0] / sv[-1]) if sv[-1] > 1e-10 else np.inf
        self._cond = raw_cond

        # EMA smoothing.
        # Non-finite raw_cond (sv[-1] ≈ 0, true singularity) drives cond_smooth
        # well above hardstop so _curve() reaches 1.0 independently of HALT,
        # which may arrive one tick later.  Previously the EMA was skipped for
        # inf, leaving cond_smooth low and producing only weak rumble.
        if np.isfinite(raw_cond):
            self._cond_smooth = (EMA_ALPHA * raw_cond
                                 + (1.0 - EMA_ALPHA) * self._cond_smooth
                                 if self._cond_smooth > 0.0 else raw_cond)
        elif self._hardstop:
            self._cond_smooth = max(self._cond_smooth, self._hardstop * 3.0)

        # ── servo status ───────────────────────────────────────────────────
        halt  = self._servo_code in (ServoStatus.HALT_FOR_SINGULARITY,
                                     ServoStatus.HALT_FOR_COLLISION)
        decel = (self._servo_code == ServoStatus.DECELERATE_FOR_APPROACHING_SINGULARITY)

        # Mark latch when HALT fires; reset recovery timer if we re-enter HALT
        if halt:
            self._in_halt    = True
            self._recovery_t = None

        # ── recovery debounce ──────────────────────────────────────────────
        # Without this, cond_smooth can linger above LOWER after HALT (EMA lag)
        # and keep _active True forever.  Once servo returns to NO_WARNING and
        # stays there for RECOVERY_DEBOUNCE seconds we trust servo over EMA and
        # force silence.  Any intervening non-NO_WARNING code (e.g.
        # DECEL_FOR_LEAVING) resets the timer so we don't clear too early.
        if self._in_halt:
            if self._servo_code == ServoStatus.NO_WARNING:
                now = self.get_clock().now()
                if self._recovery_t is None:
                    self._recovery_t = now
                elif (now - self._recovery_t).nanoseconds * 1e-9 >= RECOVERY_DEBOUNCE:
                    self._in_halt     = False
                    self._active      = False
                    self._intensity   = 0.0
                    self._cond_smooth = 0.0   # reset EMA so next approach starts clean
                    self._recovery_t  = None
                    return
            else:
                self._recovery_t = None   # e.g. DECEL_FOR_LEAVING: restart countdown

        # ── auto-calibration ───────────────────────────────────────────────
        if not self._cal_done and self._servo_code == ServoStatus.NO_WARNING \
                and np.isfinite(raw_cond):
            now = self.get_clock().now()
            if self._cal_start is None:
                self._cal_start = now
            elapsed = (now - self._cal_start).nanoseconds * 1e-9
            self._cal_conds.append(raw_cond)
            if elapsed >= CALIBRATION_WINDOW:
                peak           = max(self._cal_conds)
                self._lower    = peak * CALIBRATION_MARGIN
                self._hardstop = self._lower * HARDSTOP_MULT
                self._cal_done = True
                self.get_logger().info(
                    f'Calibration complete — peak_cond={peak:.1f}  '
                    f'LOWER={self._lower:.1f}  HARDSTOP={self._hardstop:.1f}  '
                    f'({len(self._cal_conds)} samples)')

        if not self._cal_done or self._lower is None:
            self._intensity = 0.0
            return

        # ── condition-number intensity ─────────────────────────────────────
        t = (self._cond_smooth - self._lower) / (self._hardstop - self._lower)
        cond_intensity = _curve(t)   # 0.0 when t ≤ 0, 1.0 when t ≥ 1

        # ── joint-limit intensity — ARM_JOINTS only ────────────────────────
        # Iterating pos_map directly would include gripper joints; a gripper
        # finger resting inside its limit margin would pin joint_intensity
        # permanently and keep the motor running when _active should be False.
        joint_intensity = 0.0
        for name in ARM_JOINTS:
            pos = pos_map.get(name)
            if pos is None:
                continue
            lim = self._joint_limits.get(name)
            if lim is None:
                continue   # continuous arm joints have no limits
            lo, hi    = lim
            clearance = min(pos - lo, hi - pos)
            if clearance < JOINT_MARGIN:
                ramp = _curve((JOINT_MARGIN - clearance) / JOINT_MARGIN)
                joint_intensity = max(joint_intensity, ramp)

        self._cond_intensity  = cond_intensity
        self._joint_intensity = joint_intensity

        # ── combine and apply servo overrides ─────────────────────────────
        final_intensity = max(cond_intensity, joint_intensity)
        if halt:
            final_intensity = 1.0
        elif decel:
            final_intensity = max(final_intensity, DECEL_INTENSITY)

        # ── single active flag with hysteresis ─────────────────────────────
        # Both the motor (_tick) and the log use this same flag so they cannot
        # report contradictory state.
        if not self._active:
            if final_intensity > ACTIVE_ENTER:
                self._active = True
        elif final_intensity < ACTIVE_EXIT:
            self._active = False

        # Apply perceptible floor: once active never drop below INTENSITY_FLOOR
        self._intensity = max(final_intensity, INTENSITY_FLOOR) if self._active else 0.0

    # ── rumble output ─────────────────────────────────────────────────────────

    def _tick(self):
        if self._device is None or self._eff_id < 0:
            return

        # Combine singularity/joint intensity with contact-force intensity.
        out = max(self._intensity, self._force_intensity)

        self._log_t += 0.1
        if self._log_t >= LOG_INTERVAL:
            self._log_t = 0.0
            lower_str = f'{self._lower:.1f}' if self._lower else 'calibrating…'
            self.get_logger().info(
                f'cond={self._cond:7.1f}  smooth={self._cond_smooth:7.1f}'
                f'  servo={self._servo_code}'
                f'  cond_i={self._cond_intensity:.3f}'
                f'  joint_i={self._joint_intensity:.3f}'
                f'  force={self._force_mag:5.1f}N force_i={self._force_intensity:.3f}'
                f'  out={out:.3f}'
                f'  active={self._active}'
                f'  [LOWER={lower_str}]')

        if out > 0.01:
            if abs(out - self._last_sent) > INTENSITY_DEADBAND:
                self._eff_id    = self._upload_effect(out)
                self._last_sent = out
            self._device.write(ecodes.EV_FF, self._eff_id, 1)   # refresh 300 ms window
        elif self._last_sent > 0.01:
            self._stop_rumble()   # erase + re-upload; don't rely on 300 ms expiry


def main():
    rclpy.init()
    node = HapticFeedback()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
