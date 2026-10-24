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

## Getting started

```sh
git clone --recurse-submodules <this repo>
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

Change a package inside its submodule, on a branch, and commit there first. Then
commit the updated submodule pointer here, so this repository records which package
commits were tested together:

```sh
git -C repos/zdt-x-driver switch -c feature/my-change
# edit, test, commit inside the submodule
python tools/test_all.py
git add repos/zdt-x-driver && git commit
```

## Protocol reference

The ZDT driver follows the second-generation closed-loop stepper manual **V1.0.5
(2026-05-27)**, which is the latest. It is titled X42S, but it covers the
X28S/X35S/X42S/X57S/X86S family (p10), which shares one X-firmware CAN protocol.
Known typos in that manual, open questions that need a real motor, and the
firmware, board-generation and frame-size compatibility rules are documented in
`repos/zdt-x-driver/README.md`.
