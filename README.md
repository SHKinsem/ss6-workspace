# SS6 workspace

Umbrella repository for the SS6 CAN motor stack. Each package is a git submodule
under `repos/` and stays independently buildable and versioned in its own repository.

| Package | Role | Depends on |
| --- | --- | --- |
| `repos/can-device-core` | One serialized CAN bus owner: device registration, RX routing, bounded TX queue, tickets | — |
| `repos/zdt-x-driver` | ZDT closed-loop stepper **X firmware** protocol for the whole family (X28S/X35S/X42S/X57S/X86S): codec, checksums, commands, telemetry, broadcast, per-frame-size current limits | can-device-core |
| `repos/dji-motor-driver` | M2006/C610 and M3508/C620 current control and feedback | can-device-core |
| `repos/ss6-bsp` | SS6 / ESP32-S3 N16R8 board policy and the TWAI `can_device::Transport` adapter, plus a motor demo | can-device-core (drivers only for the demo) |

The board support package does not contain motor protocols. Motor drivers do not
contain board or GPIO knowledge. Applications (Babytech, Tenny) own scheduling,
safety policy, persistence and network interfaces.

## Status

| Item | State |
| --- | --- |
| [zdt-x-driver#1](https://github.com/SHKinsem/zdt-x-driver/pull/1) | Open. X-firmware family support. It moves in the field protocol coverage (checksums, commands, telemetry, timed return, broadcast) and adds the profile and current ceiling |
| [ss6-bsp#1](https://github.com/SHKinsem/ss6-bsp/pull/1) | Open. Adopts the modular TWAI adapter, which removes the duplicated CAN/X42S code, and adds the motor demo. Merge it **after** zdt-x-driver#1 |
| Host tests | 16/16 CTest tests and the motor demo pass. The ss6-bsp X/DJI integration passes 58 checks |
| Hardware | **Not tested.** See the hardware checklist below |
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

All tests use fake transports or a fake ESP-IDF HAL. Nothing here has been run
against a physical SS6 board or motor.

## Working across packages

1. Branch inside the submodule, change it, run `python tools/test_all.py`, and commit there.
2. Push the branch and open a pull request in that package's repository. Merge it with
   **"Create a merge commit"**. Squash and rebase rewrite commit hashes, which breaks
   the submodule pointers recorded here.
3. When a change spans packages, merge the dependency first: core, then drivers, then ss6-bsp.
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
| 1 | `1A` option-status reply: 1 or 2 data bytes? (p77 table against prose) | Send `A 1A 6B` and record the reply length |
| 2 | `39` temperature sign (p72 against p96) | Read `39` and `43` at room temperature and compare the sign bytes |
| 3 | `31` linear-encoder range on 14-bit (V1.0) boards | Rotate one turn by hand while reading `31` |
| 4 | Do X28S/X35S support `C5/C6/CB/CD`? (p29 names only X42S/Y42) | Send unloaded `C5` with a small current and limit, then read the reply code (`02` or `E2`/`EE`) |
| 5 | `1F` HW_Type codes (7 codes listed for 6 sizes) | Read `1F` on each frame size and record the HW word |

Items 1–3 and 5 are read-only. Item 4 moves the motor, so run it unloaded with a low
current and speed limit.
