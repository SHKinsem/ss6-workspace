# Joint control: requirements and direction

Status: requirements agreed with the project owner on 2026-11-08. Nothing in the
"Direction" or "Roadmap" sections is implemented yet. This file is the hand-off point for
anyone continuing the control work. Keep it current: when a requirement changes or an
open question is answered, edit it here.

**Current phase [owner, 2026-11-08]:** the main work now is a **demo that tests the SS6
board, the CAN library (can-device-core plus the ss6-bsp TWAI adapter) and the ZDT motors
(zdt-x-driver) as completely as possible on hardware**. The joint controller described
here is the end goal. Use it to avoid design choices that would block it, but do not let
it take priority over the hardware coverage work.

**Layering [owner, 2026-11-08]:**
- Each application gets **its own repository**, which composes the generic libraries
  built here: can-device-core, ss6-bsp, zdt-x-driver, pid-control, device-console,
  wifi-setup, web-console, wifi-ota, and later a kinematics or trajectory library.
- ss6-probe and ss6-control are demo and test applications. The joint robot is a
  separate, future application repo.
- **Mechanism specifics are application layer**: link dimensions, assembly mode, frames,
  gear ratio, joint limits and per-robot tuning. Libraries take these as parameters and
  must not hard-code any of them.

**Library acceptance goals [owner, 2026-11-09]:** before more features, the stack must
guarantee three things. The guiding idea is "as brainless as Arduino".

1. **The application-level API is simple.** Calling the library takes a few obvious
   functions. The application never handles tickets, phases, quarantine or stream setup.
2. **Two motors run smoothly at 500 Hz.** Today's single loop does not: at 500 Hz, with
   HTTP serving, a torque frame missed its deadline and the axis faulted (2026-11-09).
3. **Debugging is powerful through composition.** There are as few and as simple console
   commands as possible, and combining them gives the stronger functions.

**Object layers and names [owner, 2026-11-09]:** each layer has its own units, and
"axis" is never a motor.

| Layer | Name | Units | Owns | Lives in |
| --- | --- | --- | --- | --- |
| Motor | `zdt_x::Motor` | motor shaft deg, rpm, mA | one ZDT motor: enable, position and velocity commands, feedback, current cap, faults; hides tickets, phases, streams and response mode | zdt-x-driver |
| Joint | `Joint` | joint deg, rpm, N·m | motor × ratio, direction, zero offset, soft limits | generic library; parameters from the application |
| Linkage | `Linkage` | mm | two joints ↔ end effector (x, y): IK, FK, Jacobian, workspace and singularity checks | kinematics library (P2a) |
| Task space | axes x, y | mm, mm/s | trajectories and interpolation | kinematics or trajectory library |

- In a parallel linkage, one motion along x moves both motors. Only the Linkage layer
  knows this.
- "Actuator" is not used. In robotics it means motor plus gearbox, which is the Joint
  layer here. The ratio is a mechanism parameter, so it stays out of the ZDT driver.
- The existing protocol-level `zdt_x::Motor` (tickets, phases, replies) is renamed
  `zdt_x::Endpoint`. The application-facing object takes the plain name. This is a
  breaking change. Babytech is out of scope **[owner]**: its code was never flashed or
  verified, so it does not constrain the API.
- **Placement [owner, 2026-11-09]:** ZDT-specific behaviour belongs in zdt-x-driver, not in
  a new package. That covers enable confirmation, the config read and response mode, the
  feedback stream and its anchoring, current-capped commands, the status watchdog and
  verified stream-off. Other parts go elsewhere:
  - the motor-agnostic real-time CAN task (TWAI plus bus, on core 1) goes in ss6-bsp;
  - generic composable console primitives go in device-console;
  - ZDT console commands are an optional module of zdt-x-driver;
  - safety policy, such as who renews the lease, stays in the application.
- **Not now:** a brand-independent motor interface shared by ZDT and DJI. Extract it only
  when an application uses both.

Each statement is tagged with where it comes from:

- **[owner]**: stated by the project owner. Treat it as a requirement.
- **[derived]**: calculated from owner requirements or from measurements.
- **[proposed]**: an engineering recommendation that is not yet agreed. Confirm it before
  building on it.
- **[open]**: not answered yet.

## 1. What is being built

| Item | Requirement |
| --- | --- |
| Load | Robot **joints** **[owner]** |
| Mechanism | 4 motors forming **two 2-DOF parallel linkages**, two motors each (for example a five-bar leg) **[owner]** |
| Control modes | **Torque control is required.** Position control comes later and may use the driver's STEP/DIR input **[owner]** |
| Motion | **Continuous trajectory tracking** **[owner]** |
| Trajectory source | Generated **in advance on a PC** and sent **probably over UDP**, in a way modelled on funscript (timestamped keyframes). The PC will most likely send **Cartesian coordinates**, and the **board solves the linkage kinematics** **[owner]** |
| Reduction | 3:1 to 6:1, through a large/small **herringbone gear** pair. The exact ratio is not fixed and the gear design is out of scope for now **[owner]** |
| Output speed | Ideally **≥ 200 rpm** at the joint **[owner]** |
| Output torque | **1–2 N·m per motor** at the joint **[owner]** |
| Supply | **20 V** **[owner]** |
| Sensing | **No output-side encoder.** Only the motor's own encoder **[owner]** |
| Motors | ZDT X42S closed-loop steppers, X firmware (bench units: FW_Ver 105, HW 0x230A), CAN at 1 Mbit/s. Ids 1–6 follow the connector slots in a U (see `repos/ss6-bsp/docs/hardware-evidence.md`) |
| Board | SS6 intermediate board (ESP32-S3 N16R8, `Revision::IntermediateKnownConflict`) |

## 2. Derived numbers

| Ratio N | Motor speed for 200 rpm at the joint | Motor torque for 1–2 N·m at the joint (η ≈ 0.95) | Joint resolution from 0x36 (0.1° at the motor) |
| --- | --- | --- | --- |
| 3:1 | 600 rpm | 0.35–0.70 N·m | 0.033° |
| 4:1 | 800 rpm | 0.26–0.53 N·m | 0.025° |
| 6:1 | 1200 rpm | 0.18–0.35 N·m | 0.017° |

**[derived]** The main feasibility risk is the speed–torque trade-off. A stepper loses
torque as speed rises, because back-EMF leaves less voltage to drive current, and at 20 V a
42-frame motor at 600–1200 rpm keeps much less than its holding torque. A higher ratio
lowers the motor torque needed but raises the motor speed needed. Measure the X42S
torque–speed curve at 20 V before fixing N. **[open]** Is 1–2 N·m needed *at* 200 rpm, or
only at low speed and stall?

**[derived]** CAN budget at 1 Mbit/s. An extended frame with 8 data bytes is about 130–150
bits, so roughly 150 µs. Per axis, each control cycle needs one F5 torque frame (8 bytes)
and one 0x36 position return (7 bytes). With a sync trigger, add one broadcast frame per
cycle.

| Axes × rate | Frames/s | Approximate bus load |
| --- | --- | --- |
| 4 × 250 Hz | 2250 | ~33% |
| 4 × 333 Hz | 3000 | ~45% |
| 4 × 500 Hz | 4500 | ~65% (ceiling: leaves little room for status reads and retries) |
| 4 × 1 kHz | 9000 | over capacity |

**[derived]** At motor speeds of hundreds of rpm, the 0.1° quantization of 0x36 does not
matter for speed estimation. It only matters when holding position and at crawl speed,
where the 0x31 linear encoder (0–65535 per revolution) would help. Its real resolution on
the X42S has not been checked.

## 2a. Measured facts: timed return (2026-11-08)

These were measured on bench X42S motors (FW 105, ids 1 and 2, disabled, 1 Mbit/s). The
diagnostic command `stream` / `streamstats` is on the ss6-control branch
`feature/stream-diagnostics` (569739d). Manual references are to the V1.0.5
transcription.

- **Rates.** 0x36, 0x31 and 0x35 all stream at 4, 2 and 1 ms exactly as configured
  (250, 500 and 1000 frames/s). Motor-side timing is tight: at 10 ms the interval is
  9.94–10.05 ms. Two motors at 1 ms (2 kHz in total) arrived without loss. TWAI reported
  0 rx-missed, 0 overruns and 0 bus errors.
- **One timed return per motor.** A new opcode 0x11 *replaces* the running stream. Any
  period-0 command stops it, whatever opcode it names. Position and speed therefore
  cannot both be streamed from one motor.
- **Streams survive an ESP32 reboot**, because they live in the motor. The control app's
  `start` must send "off" to every motor.
- **Commands can be lost.** One "off" got no reply and the stream kept running; a retry
  worked. Every safety-relevant command needs confirmation and retry. ZDT commands and
  replies share a CAN ID, and the transport sends each frame once.
- **The ESP32 loop is the bottleneck, not the bus.** With Wi-Fi and HTTP on the same
  loop, frames are read up to about 10 ms late and about 20% arrive bunched together. At
  4 motors × 1 kHz, a 10 ms stall is about 40 frames, more than the 32-frame RX queue.
  This confirms the core-1 control task (4.3).
- **At standstill** 0x31, 0x35 and 0x36 are perfectly constant (sd 0).
- **Manual facts:**
  - 0x31 is 0–65535 per turn and wraps every turn. The board may have a 14-bit encoder
    (V1.0 boards) or a 16-bit one (V2.0 boards).
  - Uncalibrated absolute accuracy is ±0.75–1.5°.
  - 0x35 is in 0.1 rpm. 0x27 is phase current in mA and can be timed-returned.
  - The driver's internal torque, speed and position loops run at 20 kHz.
  - C5 is F5 plus a maximum speed in 0.1 rpm.
  - F5 and C5 honour the sync flag plus the `00 FF 66 6B` trigger.
- **0x31 is true 16-bit on the bench X42S (motor 1).** In a hand-turn test, 10005 frames at
  1 ms gave 4365 distinct values with smallest step 1 and gcd step 1, so about 0.0055°
  per count, 18× finer than 0x36.
- **[proposed]** Stream 0x31 for feedback and unwrap the turns on the ESP32. Anchor and
  check the turn count against a 0x36 read at enable and at a low rate afterwards.
  Derive speed from 0x31. Decide after the resolution test.

## 3. Where the code is today

`repos/ss6-control` (see its sources for details):

- A single position PID produces a current command, sent as ZDT `F5` without waiting for a
  reply. Feedback is the `0x36` timed return at the loop rate, currently configured to
  250 Hz. Effects are confirmed by `3A` status reads every 200 ms.
- Console, CAN, control, Wi-Fi, HTTP and OTA share **one Arduino loop task**.
- Speed is the difference of two 0.1° positions, divided by an `ms` receive timestamp.
- Safety:
  - Motors start disabled.
  - Per-axis current limit (default 150 mA), also set as the driver profile ceiling.
  - Speed clamp, plus faults for overspeed, maximum error, feedback timeout and status.
  - 3 s heartbeat lease.
  - E-stop. OTA stops the motors first.
- Bench result, unloaded, no gearbox: ±10° steps at 150 mA. At kp 10, ki 20, kd 2 the
  motor shows a **±6° stick-slip limit cycle**. Detent torque plus friction need about
  50–75 mA, and the integrator hunts against it.
- There is a web page with live charts. The chart's current is the *commanded* F5 value,
  not the measured phase current, and its speed is derived from position.

## 4. Direction **[proposed]**

> **Owner decision, 2026-11-09:** pause the external torque loop (4.1) and use the
> driver's own position and velocity loops (4.2) for now. Their current-capped forms
> (`CB`/`CD` position, `C6` velocity) keep the per-axis current limit. Revisit current
> control when ZDT releases its CANopen firmware and examples; the owner expects that to
> allow finer current control. **[owner]**
>
> Why: on the unloaded X42S, a 200 Hz external loop through F5 stick-slips. Static friction
> is above kinetic friction (about 60 vs 45–55 mA), and the 20 rpm clamp zeroes the output
> at every slip. Friction feed-forward and 0x31 feedback helped (tracking sd 4.1 → 2.5°)
> but did not remove it. Details are in `docs/hardware-coverage.md`, "Control findings".

### 4.1 One control law: joint impedance

```
tau_cmd = Kp·(q_ref − q) + Kd·(qd_ref − qd) + tau_ff
I_cmd   = tau_cmd / (Kt · N · η)            (clamped, sent as F5 / C5)
tau_ff  = J·qdd_ref + friction(qd) [+ gravity / interaction terms later]
```

- **Torque mode** is small or zero Kp and Kd, with only `tau_ff` (a desired torque plus
  compensation).
- **Position tracking** is high Kp and Kd plus inertia feed-forward.

Both are the same loop with different gains, so switching modes does not mean switching
controllers. Trajectory points carry q, qd and qdd. Friction feed-forward (Coulomb plus
viscous) replaces the integrator as the fix for stick-slip.

### 4.2 Driver-side position mode, later

For stiff position control, let the driver close the loop internally. Its internal loop
runs far faster than an external 250–500 Hz CAN loop. There are two ways to feed it:

- stream `positionDirect` setpoints over CAN, using the sync flag and
  `zdt_x::Broadcast::syncTrigger`;
- STEP/DIR pulses from the ESP32 (RMT).

Both should consume the same trajectory buffer as the impedance mode. On a switch, the
driver target is set to the current position so the switch is bumpless.

**Hardware constraint [derived]:** on the intermediate board, motor slot **id 4 DIR is
GPIO37**, an octal-PSRAM line, and is unusable (`ss6-bsp` `Board.h`). STEP/DIR on four
axes therefore needs slots **1, 2, 3, 5**, or the adjusted board revision. The CAN
position stream has no such limit.

### 4.3 Real-time structure

Move the CAN bus and the control loop to a **dedicated high-priority FreeRTOS task pinned
to core 1**. Console, Wi-Fi, HTTP, UDP and OTA stay on the other task and talk to it
through queues or double-buffered state. Today a Wi-Fi or HTTP stall delays the control
cycle. Also:

- time samples with `micros()`, or use the nominal stream period;
- issue all four axes' commands with the sync flag plus one broadcast trigger per cycle,
  so the two linkages actuate on the same instant.

Target: 4 axes at 333–500 Hz. Measure the cycle jitter and drop counts, then pick the
rate.

### 4.4 Trajectory input

- **[owner]** The PC sends **Cartesian** end-effector coordinates, one point per linkage.
  The **firmware owns the kinematics** of both 2-DOF parallel linkages.
- **[proposed]** Kinematics on board:
  - The geometry parameters of each linkage (link lengths, base spacing, frame origin and
    orientation, assembly-mode branch, gear ratio) belong to the **joint application**. It
    stores them in NVS, can change them at run time, and passes them to the generic
    kinematics library.
  - Closed-form inverse kinematics, run every control cycle. For a planar five-bar it is two
    circle intersections, cheap in single-precision float on the ESP32-S3. Closed-form
    forward kinematics gives the measured end-effector position.
  - Interpolate in Cartesian space, run IK at each cycle, and get the joint q̇ and q̈
    feed-forward by finite differences of the IK'd trajectory, or through `J⁻¹`.
  - The workspace check comes before execution. A keyframe outside the reachable
    workspace, too close to a singularity (distal links near collinear, or `det J` near 0),
    or beyond the joint limits is rejected when it is received. At run time, nearing a
    singularity stops the linkage.
  - Cartesian impedance falls out naturally:
    `tau = Jᵀ·(Kx·(x_ref − x) + Dx·(ẋ_ref − ẋ) + F_ff) + joint feed-forward`. Stiffness
    can then be set per Cartesian direction.
- Protocol: funscript-like, but adapted:
  - timestamped keyframes per linkage, in Cartesian units (mm), not funscript's 0–100.
    They may optionally carry a velocity, and later a stiffness or force;
  - optional velocity per keyframe;
  - sent ahead of time over UDP;
  - buffered on the ESP32 and interpolated on board (cubic or quintic, so qd and qdd are
    continuous).
- Points are **never streamed one at a time in real time**, because Wi-Fi jitter is tens
  of milliseconds.
- Needed: a playback clock synchronized to the PC, sequence numbers with loss detection,
  and a buffer-underrun behaviour (hold, then stop).
- Note on funscript: it is JSON `{"actions":[{"at":<ms>,"pos":0..100}]}`, one axis per
  script, and players interpolate linearly. Use it as a model, not as the wire format.

### 4.5 No output encoder: consequences

- **Homing is required.** The motor encoder is absolute within one turn. Through N:1 that
  leaves N candidate joint positions, and the linkage adds more. Proposed approach:
  sensorless homing, driving each joint at low torque into a hard stop in torque mode and
  detecting it by the speed falling to zero.
- Gear backlash sits outside the loop. It does not cause oscillation, but it shows up
  directly as joint position error.
- Joint torque is estimated as `I · Kt · N · η`. Kt must be calibrated (lever plus scale),
  and gear friction biases the estimate.

### 4.6 Units and safety for these speeds

- Add a per-axis ratio parameter. Targets, limits and display are in **joint** degrees,
  rpm and N·m.
- Current limits sized for 1–2 N·m will be around amps, not 150 mA. Watch motor
  temperature: holding torque in torque mode means continuous current.
- Required protections:
  - per-joint **soft position limits**;
  - lease shortened to **0.3–0.5 s** (3 s is about 60 motor turns at 1200 rpm);
  - `C5` (torque with a speed limit) instead of `F5`, so the driver caps speed itself;
  - tracking-error collision detection;
  - stop on trajectory buffer underrun.
- Current, voltage and speed increases on hardware happen only with the owner present and
  agreeing (this has been the working rule on the bench).

## 5. Roadmap **[proposed]**

| Phase | Content | Done when |
| --- | --- | --- |
| P0 Foundation | Control task on core 1; `micros` timing; jitter and drop statistics; ratio and joint units; soft limits; short lease; `C5` | Jitter measured at 250/333/500 Hz with Wi-Fi busy; no missed cycles |
| P0 Measure | Torque–speed curve of X42S at 20 V; Kt calibration; 0x31 resolution | Ratio N chosen with data |
| P1 Impedance | Control law 4.1, friction and inertia feed-forward, 4-axis sync | Stick-slip gone; step and sine tracking error within target **[open: target]** |
| P2a Kinematics | Linkage IK/FK/Jacobian, workspace and singularity checks, as a separate host-tested header-only package (like pid-control), with no platform dependency. The geometry is a parameter; the robot's dimensions live in the joint application repo | Host tests: IK∘FK round trip, Jacobian against finite differences, rejection at the workspace edge |
| P2b Trajectory | UDP keyframe protocol in Cartesian coordinates, on-board buffer, Cartesian interpolation plus IK per cycle, clock sync, PC sender tool | Two linkages replay a PC-generated trajectory together |
| P3 Position mode | Driver-internal position via CAN stream or STEP/DIR, bumpless switching, sensorless homing. **Moved ahead of P1 on 2026-11-09 (owner)**: the first step is current-capped `CB`/`CD`/`C6` commands in ss6-control, which is also the first multi-frame TX on hardware | Joint repeats a trajectory after homing |

## 6. Open questions

1. Is 1–2 N·m needed at 200 rpm, or only at low speed and stall? This decides whether
   the X42S at 20 V is sufficient.
2. Tracking accuracy and bandwidth targets at the joint (degrees of error, Hz).
3. Answered: the PC sends Cartesian coordinates and the board does the kinematics. Still
   open:
   - The exact linkage type. Is it a planar five-bar (2-RRR) or something else?
   - Its dimensions.
   - The working (elbow) mode.
   - Whether the two linkages share one frame (for example a body frame) or each has its
     own.
   - Whether keyframes carry only position, or also velocity, stiffness or force.
4. Final ratio N, and the herringbone gear backlash (deferred by the owner).
5. Joint range of motion and the location of the hard stops, for homing and soft limits.
6. UDP details: is the PC on the same LAN? Is the ESP32 a station or the AP? What is the
   acceptable start latency?
