# SS6 workspace

Umbrella repository for the SS6 CAN motor stack. Each package is a git submodule
under `repos/` and stays independently buildable and versioned in its own repository.

| Package | Role | Depends on |
| --- | --- | --- |
| `repos/can-device-core` | One serialized CAN bus owner: device registration, RX routing, bounded TX queue, tickets | — |
| `repos/zdt-x-driver` | ZDT closed-loop stepper **X firmware** for the whole family (X28S/X35S/X42S/X57S/X86S). `zdt_x::Motor` is the application API: one object per motor, with start-up checks, response mode, feedback, current-capped position and velocity, and watchdogs. `zdt_x::Endpoint` is the protocol layer: codec, checksums, commands, telemetry, broadcast, per-frame-size current limits | can-device-core |
| `repos/dji-motor-driver` | M2006/C610 and M3508/C620 current control and feedback | can-device-core |
| `repos/pid-control` | Header-only discrete PID, float and Q16.16 fixed point: D on measurement, conditional-integration anti-windup, clamp, slew, setpoint weighting. Host-tested | — |
| `repos/ss6-tcode` | TCode v0.3/v0.4 parser and per-axis interpolator (host-tested); the ESP32 TCode receiver firmware (UDP 8000, mDNS tcode.local, axis L0 to one motor) is in progress | — (library) |
| `repos/device-console` | Allocation-free line console: command registry, local/remote sources, ring log for remote readers. Host-tested, no platform dependency | — |
| `repos/ss6-bsp` | Everything SS6 / ESP32-S3: board policy and pins, the TWAI adapter, `CanTask` (the bus in a 500 Hz task on core 1), Wi-Fi setup, web console, OTA | can-device-core, device-console |
| `repos/ss6-control` | **Application.** Demo and test firmware: motors 1–6 through `zdt_x::Motor` on `ss6::CanTask`, with commands over USB and Wi-Fi and OTA | all of the above except dji-motor-driver and pid-control |

Merged or retired on 2026-11-09:

- wifi-setup, web-console and wifi-ota are now part of ss6-bsp, with their history.
- ss6-probe is retired. Its diagnostics are to return as ss6-control debug commands.
- The external torque controller is removed from ss6-control. Tag
  `archive/torque-pid-2026-11-09` keeps it.

The old repositories stay on GitHub.

Requirements and planned direction for the joint controller (torque control, trajectory
tracking, gearing, roadmap, open questions): [docs/joint-control-requirements.md](docs/joint-control-requirements.md).

The board support package does not contain motor protocols. Motor drivers do not
contain board or GPIO knowledge. Applications (Babytech, Tenny) own scheduling,
safety policy, persistence and network interfaces.

## Status

Native Wi-Fi motor firmware upgrade: the address-1 X42S FW207 checkpoint passed a
real 87-second run on 2026-11-09. Later that day the multi-address / multi-image version
(address 1–6, X42S V2.0.1–V2.0.7 by full SHA256) took address 2 from FW107 through FW206
to FW207, leaving address 1 untouched. The first step needed a manual communication-setting
fix on the motor. The owner requested completion as a supported feature;
see [checkpoint, limitations and completion checklist](docs/native-iap-roadmap.md).
Exact tested revisions and evidence are recorded there. It is merged into every package's
`main`, and the submodule pointers here include it (2026-11-10).

| Item | State |
| --- | --- |
| [zdt-x-driver#1](https://github.com/SHKinsem/zdt-x-driver/pull/1), [ss6-bsp#1](https://github.com/SHKinsem/ss6-bsp/pull/1) | Merged: X-firmware family support; modular TWAI adapter and motor demo |
| [ss6-bsp#3](https://github.com/SHKinsem/ss6-bsp/pull/3), [zdt-x-driver#2](https://github.com/SHKinsem/zdt-x-driver/pull/2), [device-console#1](https://github.com/SHKinsem/device-console/pull/1), [web-console#1](https://github.com/SHKinsem/web-console/pull/1) and [#2](https://github.com/SHKinsem/web-console/pull/2), [ss6-probe#1](https://github.com/SHKinsem/ss6-probe/pull/1) and [#2](https://github.com/SHKinsem/ss6-probe/pull/2), [ss6-control#1](https://github.com/SHKinsem/ss6-control/pull/1) and [#2](https://github.com/SHKinsem/ss6-control/pull/2) | Merged (2026-11-08). They cover: motor ids by U-shaped slot; control commands without replies; quiet commands; a page served from LittleFS and uploadable without a reflash; probe OTA and the run-time bitrate; control live charts, stream diagnostics, a start-up sweep (verified stream-off plus disabling motors found enabled) and a log-duplication fix. Every package in this repository is pinned to its `main` |
| [zdt-x-driver#3](https://github.com/SHKinsem/zdt-x-driver/pull/3), [ss6-bsp#4](https://github.com/SHKinsem/ss6-bsp/pull/4), [ss6-control#5](https://github.com/SHKinsem/ss6-control/pull/5) | Merged (2026-11-09): `zdt_x::Motor` and `Endpoint`, `ss6::CanTask` and the folded-in board services, and ss6-control on the new API without the torque controller. Tracking issues: [ss6-control#3](https://github.com/SHKinsem/ss6-control/issues/3) (torque control, paused) and [#4](https://github.com/SHKinsem/ss6-control/issues/4) (the probe diagnostics as debug commands) |
| [zdt-x-driver#4](https://github.com/SHKinsem/zdt-x-driver/pull/4) and [#5](https://github.com/SHKinsem/zdt-x-driver/pull/5), [ss6-bsp#5](https://github.com/SHKinsem/ss6-bsp/pull/5), [ss6-control#6](https://github.com/SHKinsem/ss6-control/pull/6) and [#8](https://github.com/SHKinsem/ss6-control/pull/8) | Merged (2026-11-10): the IAP protocol docs and the `zdt_x::Iap` engine; the gs_usb USB-to-CAN bridge (`ss6_usbcan`); the Wi-Fi motor firmware upgrade at `/iap`. Every package in this repository is pinned to its `main` |
| [ss6-bsp#6](https://github.com/SHKinsem/ss6-bsp/pull/6), [ss6-tcode#1](https://github.com/SHKinsem/ss6-tcode/pull/1), [zdt-x-driver#6](https://github.com/SHKinsem/zdt-x-driver/pull/6) | Merged (2026-11-10). They cover: up to 5 saved Wi-Fi networks (`wifi list`, `wifi forget`), with the strongest saved network and access point chosen; the UDP TCode firmware with the STEP/DIR drive mode; `MotorConfig::external`. Every package in this repository is pinned to its `main` |
| [ss6-bsp#7](https://github.com/SHKinsem/ss6-bsp/pull/7), [ss6-tcode#3](https://github.com/SHKinsem/ss6-tcode/pull/3), [zdt-x-driver#7](https://github.com/SHKinsem/zdt-x-driver/pull/7) | Merged (2026-11-10). They cover: a 12 s Wi-Fi join grace (busy sites); `m <id> cfg set interp` and `m <id> read <hex>` (raw motor reads, e.g. PID); per-package `CLAUDE.md` notes for agents. The STEP/DIR bench results are in `docs/hardware-coverage.md`. Every package in this repository is pinned to its `main` |
| Host tests | All host tests and the motor demo pass (`tools/test_all.py`). ss6-control builds with PlatformIO (`ss6_intermediate`, `ss6_usbcan`) |
| Hardware | Bench-tested on the intermediate board with two X42S (FW_Ver 105, addresses 1 and 2) at 1 Mbit/s, unloaded: reads, timed-return streams at 1–10 ms (one per motor; 0x31 is true 16-bit), Wi-Fi, OTA and the page upload; ss6-control closed loop ±10° at 150 mA. What is and is not proven, and the test plan, are in [docs/hardware-coverage.md](docs/hardware-coverage.md) |
| Babytech `feature/astra-ss6-migration-20261020` | Still pinned to the pre-PR zdt-x-driver. Rebuild it against the merged driver before it switches |

The submodules are private repositories. Cloning them needs read access to
`SHKinsem/*`; without it, this repository only shows the layout and the pinned commits.

## Getting started

```sh
git clone --recurse-submodules https://github.com/SHKinsem/ss6-workspace.git
# or, in an existing checkout:
git submodule update --init
```

Run every package's host tests and the motor demo (needs a C++17 compiler, CMake
and Ninja; `pip install cmake ninja` is enough):

```sh
python tools/test_all.py
```

On Windows it builds under `%TEMP%\ss6-build`, because deep OneDrive paths overflow
MAX_PATH in generated object paths. The same umbrella build by hand:

```sh
cmake -S . -B build -DSS6_BUILD_MOTOR_DEMO=ON
cmake --build build
ctest --test-dir build --output-on-failure
```

All host tests use fake transports, a fake ESP-IDF HAL or a simulated motor. Hardware
results are in [docs/hardware-coverage.md](docs/hardware-coverage.md).

The firmware is built with PlatformIO, not CMake:

```sh
cd repos/ss6-control
pio run -t upload --upload-port COMx && pio device monitor --port COMx
pio run -e ss6_intermediate_ota -t upload --upload-port <board ip>   # over Wi-Fi
```

## Working across packages

1. Branch inside the submodule, change it, run `python tools/test_all.py` from the
   workspace root, and commit there.
2. Push the branch and open a pull request in that package's repository. Merge it with
   **"Create a merge commit"**. This repository may already pin the PR's pre-merge
   commits; squash and rebase leave them unreachable once the branch is deleted. Only
   pin commits reachable from the package's `main`.
3. When a change spans packages, merge the dependency first: can-device-core and
   device-console, then the drivers and ss6-bsp, and ss6-control last.
4. Commit the updated submodule pointers here, through a pull request too, so this
   repository records which package commits were tested together.

```sh
git -C repos/zdt-x-driver switch -c feature/my-change
# edit, test, commit, push and open a PR inside the submodule
python tools/test_all.py
git switch -c bump/zdt-my-change && git add repos/zdt-x-driver && git commit
```

## ZDT compatibility at a glance

The rules below come from manual V1.0.5. Details and page references are in
`repos/zdt-x-driver/README.md`.

- **Firmware:** X firmware only. Emm firmware uses different payloads for the same
  opcodes. An Emm `43` reply (`43 1F 09`) is detected and discarded.
- **Board generation:** second generation is the default. The discontinued X42_V1.3
  (`Legacy`) lacks timed return `11`, hybrid `C5/C6/CB/CD` and single-command
  multi-motor `00 AA` (p7). `00 FF 66` sync works on both.
- **Firmware version:** fast position `F1`/`FC` needs FW_Ver ≥ 200, i.e. V2.0.0 (p58–59).
- **Frame size (current ceiling):** the protocol field limit is 5000 mA (`0x1388`).
  Each frame size caps it further:

  | Frame | Rated current (p10) | Driver ceiling |
  | --- | --- | --- |
  | 20 (HW_Type 0) | Not listed | 5000 mA (field limit) |
  | 28 (X28S) | 0–3000 mA | 3000 mA |
  | 35 (X35S) | 0–4000 mA | 4000 mA |
  | 42 (X42S) | 0–5000 mA | 5000 mA |
  | 57/86 (X57S/X86S) | 0–6000 mA | 5000 mA (field limit) |
  | Unknown | — | 5000 mA |

  An application can set a stricter `currentLimitMa`, never a looser one. The frame
  size comes only from an explicit `adoptObservedVersions()` after reading `1F`.
- **Checksums:** fixed `0x6B`, XOR or CRC-8, set per motor. Modbus and DMX are not supported.
- **"(X42S/Y42)" in the manual** means "common to both firmwares" (p46). It is not a
  board list and is not used for gating.

## Manual findings

The manual is titled X42S, but its p10 table covers the X28S/X35S/X42S/X57S/X86S family.

- **Latest version:** V1.0.5 (2026-05-27). The disputed passages were checked against
  the original PDF, not only the Babytech transcription.
- **No command changed format between versions.** The revision history (p1) only adds
  material:
  - V1.0.2 adds the `0x12` homing reply.
  - V1.0.4 adds fast position `F1`/`FC` and the multi-motor CAN example.
  - V1.0.5 adds 2.0-board encoder and supply descriptions.

  The field implementation followed V1.0.3, so it predated `F1`/`FC`.
- **Real compatibility axes:** firmware type (X/Emm), firmware version (≥ V2.0.0 for
  `F1`/`FC`), board generation (X42_V1.3 against second generation) and frame size
  (rated current).
- **Typos in the original PDF**, handled in the driver:
  - The `0x7E30` speed limit is really 30000 = `0x7530`; the vendor STM32 sample also
    uses 3000.0 RPM.
  - `0B80` is labelled 3000 mA; it is kept as 2944.
  - The `02 11 6B` timed-return ack is missing its status byte; both forms are accepted.
  - The header byte numbers of the `21` and `49` replies are misnumbered.
- **Packing confirmed by the vendor STM32 sample (`X_V2.c`):** every CAN fragment
  repeats the opcode, with 7 data bytes per frame. The `00 AA` length is the embedded
  bytes plus 5.
- The manual's `AA`, `F6`, `FD` and `F1` worked examples use **Emm** layouts. The X
  driver refuses them as X commands.

## Hardware checklist

The driver deliberately leaves these open until they are seen on a real motor. Use a
CAN analyser or the BSP adapter at the motor's configured bitrate:

| # | Question | How to settle it |
| --- | --- | --- |
| 1 | `1A` option-status reply: 1 or 2 data bytes? (p77 table against prose) | Send the raw frame `<addr> 1A 6B` from a CAN analyser (the driver refuses `1A`) and record the reply length |
| 2 | `39` temperature sign (p72 against p96) | Read `39` and `43` at room temperature and compare the sign bytes |
| 3 | `31` linear-encoder range on 14-bit (V1.0) boards | Rotate one turn by hand while reading `31` |
| 4 | Do X28S/X35S support `C5/C6/CB/CD`? (p29 names only X42S/Y42) | Send unloaded `C5` with a small current and limit, then read the reply code (`02` or `E2`/`EE`) |
| 5 | `1F` HW_Type codes (7 codes listed for 6 sizes) | Read `1F` on each frame size and record the HW word |

Items 1–3 and 5 are read-only. Item 4 moves the motor, so run it unloaded with a low
current and speed limit.
