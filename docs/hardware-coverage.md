# Hardware test coverage

This is the current phase: a demo that exercises the SS6 board, the CAN library and the
ZDT motors as completely as possible on real hardware. This file tracks what has been
proven on hardware and what has not, and the planned test order. Update the "Verified"
column as tests pass, with the date and any evidence.

- First compiled on 2026-11-08 from a source inventory. Line references are in
  `repos/<pkg>/src/...` at that date.
- Bench: two ZDT X42S motors (FW_Ver 105, HW 0x230A, ids 1 and 2) on the intermediate
  board, 1 Mbit/s, 20 V, unloaded.

Risk classes:

| Class | Meaning |
| --- | --- |
| R0 | read-only |
| R1 | state change without motion |
| R2 | low-current, low-speed, unloaded motion |
| R3 | persistent or link configuration (can lose communication) |
| R4 | board-level fault injection |

R2 and above need the owner present and agreeing.

## Key facts

- **Multi-frame transmit has not been proven on hardware.** Every command sent so far (F3,
  F5, FE, 11, all reads) fits in one frame. Multi-frame *receive* is proven by the 42
  reply (5 frames). Multi-frame commands, with the number of frames each takes, are C5 2,
  FB 2, FD 2, CB 2, F1 2, CD 3, 4C 3, 4A 3, 48 5 and AA up to 8 (`Driver.cpp:138-151`).
- **Most of the driver is unused by the apps.** Nothing has yet exercised Broadcast,
  velocity, position, home, zero, clearProtection, the config write path, `torqueLimited`,
  `velocityLimited` or `submitLogical`.
- **F1/FC need FW_Ver ≥ 200.** The bench motors are at 105, so only the negative test
  (`UnsupportedByProfile`) is possible.
- **Some writes cannot be made through the library, by design.** It never changes
  address, checksum mode, bitrate or port, and refuses `48 D1` with
  `UnsupportedLinkChange` (`Driver.cpp:486-492`). Testing those needs a raw or test-only
  path, on a spare motor.
- **The BSP has software for CAN only.** STEP/DIR, aux, RGB, UART, SPI, J1 and HX711 exist
  only as evidence tables (`Board.h:111-117,197-198`). Testing those pins needs
  application GPIO code.
- **Pins that cannot be used on this board:**
  - RGB (GPIO35), J1.1 (36) and slot-4 DIR (37) are octal-PSRAM lines.
  - Aux STEP/DIR (46/3) are strapping pins that `validatePin` rejects (`Board.h:88,161`).

## Verified so far (2026-11-08)

- **Board:**
  - CAN TX7/RX6 at 1M and 500k, including switching the bitrate at run time.
  - RX at about 2000 frames/s with 0 missed and 0 overruns.
  - USB CDC console, Wi-Fi STA and AP, OTA (about 14 s for 850 KB).
  - NVS, the web server, and the LittleFS page store (upload in 0.5 s, 401 on a bad
    token, fallback to the embedded page).
- **can-device-core:**
  - attach and RX routing for 2 motors plus a raw sender;
  - TX ControllerAccepted;
  - timeouts and quarantine;
  - bus rebuild on a bitrate change.
- **zdt-x-driver:**
  - reads 1F, 42 (5-frame RX), 36, 3A, 31 and 35;
  - timed return 11 at 1–10 ms for 36, 31 and 35. Only one stream per motor; a new one
    replaces the old; period 0 stops any stream; streams survive an ESP32 reboot;
  - F3, F5 and FE with `expectReply=false` (Response=1);
  - closed loop ±10° at 150 mA;
  - 0x31 is true 16-bit.

## Coverage matrix

### ss6-bsp

| Feature | Verified | How to test | Risk |
| --- | --- | --- | --- |
| CAN TX7/RX6, 1M/500k, run-time switch | Yes | — | R0 |
| Transport status: Running and counters | Partly. BusOff, Recovering and Stopped not seen | R4-1 | R0/R4 |
| Transport errors (`TransmitFailed`, `NotRunning`) | Partly | R4 tests | R4 |
| `txReadiness` Busy deferral, single-shot | Partly. TX is low rate | multi-frame TX plus `can stress` | R2/R4 |
| Bus-off recovery | No. There is no API, only close + configure + start | R4-1 | R4 |
| STEP/DIR ×6 (5/4, 16/15, 18/17, 38/37, 40/39, 42/41) | No | new `pins` command, scope on a bare connector | R1 |
| Aux STEP/DIR 46/3 | No | `pins aux`, after boot only (strapping pins) | R1 |
| J1 (13/1/2), SPI, HX711 | No | `pins loop` | R1 |
| UART 43/44 | No | `uart loop`. The console is USB CDC, so UART0 is probably free **(inf)** | R1 |
| PSRAM 8 MB, flash 16 MB | No | `ESP.getPsramSize()` | R0 |
| RGB | Impossible on this board (PSRAM) | — | — |

### can-device-core

| Feature | Verified | How to test | Risk |
| --- | --- | --- | --- |
| Attach, routing, `unmatchedRx`/`invalidRx` | Yes | `bus` | R0 |
| Duplicate id, route conflict, PoolFull | Host tests only | `can stress` | R1 |
| Bounded TX queue (16 jobs, 8 frames per batch) | Partly (depth 1) | `can stress`: expect PoolFull and InvalidFrame | R1 |
| TxState Failed, Partial, Expired, Cancelled | No | R4 tests and stress | R4 |
| Inter-frame gap, head-of-line wait | No | any multi-frame command | R2 |
| Status gating (Stopped, BusOff, Recovering fail queued jobs) | No | R4-1 | R4 |
| Error-passive, error counters, alerts | No. There is no concept in the core (`Core.h:9,11`) and no alerts configured | needs `can stat` | R4 |

### zdt-x-driver

Reads:

| Opcode | Verified | How to test | Risk |
| --- | --- | --- | --- |
| 1F, 42, 36, 3A, 31, 35 | Yes | — | R0 |
| 24, 26, 27, 32–34, 37, 39, 3B–3D, 43 | No | probe `read`/`watch`, or a new `m read` in control | R0 |
| 13, 16, 20–23, 38, 3F, 41, 49 | No. These replies are not decoded (`Telemetry.cpp:70`); see them with `trace` | `read` plus `trace` | R0 |
| 1A | No. The driver refuses it (README checklist 1) | `raw 100 1A 6B` plus `trace` | R0 |
| Timed return for the remaining info opcodes | No | `stream <id> <op> <ms>` | R0 |
| Stream interleaved with a multi-frame read (42/43) | Unknown | stream on, then read 42/43 | R0 |

Commands:

| Feature | Verified | How to test | Risk |
| --- | --- | --- | --- |
| F3, F5, FE | Yes | — | R1/R2 |
| C5 (2 frames; README checklist 4) | No | new `m move torquelim` | R2 |
| F6, C6 velocity | No | new `m move vel` / `vellim` | R2 |
| FB, CB, FD, CD position (3 PositionModes) | No | new `m move pos` / `poslim` / `trap` / `traplim` | R2 |
| F1/FC | Impossible on FW 105 | negative test only | R2 |
| 9A homing, 9C interrupt | No | new `m move home` / `homeint` | R2/R1 |
| 93 88 zero position, 0A 6D zero angle, 0E 52 clear stall | No | new `m param` | R1 (save=1: R3) |
| Sync flag plus `00 FF 66` trigger | No | raw, or new `b trigger` | R2 |
| AA multi-motor | No | new `b multi` | R2 |
| `expectReply=true` control commands | No. Needs Response ≠ 1 | after an R3 Response change | R1/R3 |
| E2/EE error replies | No | raw with an out-of-range argument plus `trace`. With Response=1 a rejection may be silent **(inf)** | R1 |
| 9F completion replies | No | Response mode that reports completion | R2/R3 |
| Config round trip (`setDesiredConfig`/`writeDesiredConfig`, save=0) | No (5-frame TX) | new `m cfg`: write back unchanged, re-read, compare | R3 until proven |
| Parameter opcodes (84, 50, D7, 46, D4, D0, 4F, 44, 45, 4A, D1, D3, 68, 4B, 5C, D6, F7, 4C) | No | new `m param <op>` | R3 |
| Checksum XOR/CRC-8 end to end | No. The library cannot set the mode | spare motor plus a test-only raw config write | R3 |
| Profile current cap (`UnsupportedByProfile`) | Partly | command above the limit | R0 |

## Testable now vs needs firmware

- **Testable now:**
  - ss6-probe: `scan`, `read`, `watch`, `trace`, `bus`, `bitrate`.
  - ss6-control: `raw` (one frame of up to 8 bytes, any id including 0; it bypasses the
    driver), `stream`/`streamstats` (TWAI missed, overrun, bus-error and arb-lost
    deltas), `trace`, `bus`, `bitrate`.
- **Needs new firmware:**
  - multi-frame TX;
  - every unused driver path;
  - `expectReply=true` control commands;
  - queue overflow;
  - bus-off recovery;
  - TWAI error counters;
  - pin tests.

Proposed hardware-test commands, which call the library rather than raw frames. Each is
gated by current and speed ceilings, the e-stop and the lease.

1. `m read|watch <id> <op>`: dump telemetry, `diagnostics().lastMessage` and `request()`.
2. `m move <id> <kind> ...`, for torque, torquelim, vel, vellim, pos, poslim, trap,
   traplim, fastset, fasttgt, stop, home and homeint. Print `StartResult`, `Phase`,
   `ReplyKind`, `replyCode` and `TxResult`.
3. `m cfg <id> read|show|set|write [save]|diff`.
4. `m param <id> zero [save]|clearstall|zeroangle|<op> <data>`.
5. `b trigger`, `b multi ...` (Broadcast).
6. `m checksum <id> fixed|xor|crc8`, plus a test-only raw config write.
7. `can stat` (full `twai_status_info_t`), `can recover`, `can stress <n> <frames>`.
8. `pins pulse|read|loop`, `uart loop` (application GPIO outside the BSP).

## Test order

Before every step and after it, keep the `bus` output.

### R0: read-only, existing commands

| # | Test | Pass criterion |
| --- | --- | --- |
| 0.1 | `raw 100 1A 6B` plus trace (checklist 1) | reply data length recorded (1 or 2 bytes) |
| 0.2 | read 39 and 43 at room temperature (checklist 2) | the sign conventions agree, plausible °C |
| 0.3 | 31 over one hand turn (checklist 3) | done on 16-bit HW 0x230A; 14-bit boards not available |
| 0.4 | `scan` (checklist 5) | HW 0x230A recorded; other frame sizes not available |
| 0.5 | read 13, 16, 20–24, 26, 27, 32–34, 37, 38, 3B–3D, 3F, 41, 43, 49 | `ReplyObserved`, `invalid` stays 0, 21 arrives as 3 frames and 43 as 5 |
| 0.6 | stream 24, 26, 27, 32–34, 37–39, 3A–3D at 5–10 ms | period ±1 ms, 0 missed |
| 0.7 | stream on, then read 42/43 | Complete, no outOfOrder or gaps |
| 0.8 | two motors at 1 ms plus raw traffic | arb-lost may rise; missed and overrun stay 0 |

### R1: state change, no motion

| # | Test | Pass criterion |
| --- | --- | --- |
| 1.1 | stop and homeint with and without a reply expected | `Sent` / `ReplyObserved`; no quarantine |
| 1.2 | out-of-range F3 via raw | E2/EE in the trace, or silence; record which |
| 1.3 | config round trip, save=0 | all 32 bytes equal (treat as R3 until it passes on a spare motor) |
| 1.4 | F3 with the sync flag, then `00 FF 66` | enabled only after the trigger |
| 1.5 | zero angle / zero position, save=0 | 36 reads about 0 |
| 1.6 | `can stress` | PoolFull at job 17, InvalidFrame at 9 frames |
| 1.7 | `pins pulse` on a bare connector | edges on the right GPIO for each slot |

### R2: low-current motion

The motors are unloaded, at 100–150 mA, at low speed and over small angles.

| # | Test | Pass criterion |
| --- | --- | --- |
| 2.1 | C5 at about 100 mA with a speed cap (checklist 4; first multi-frame TX) | the motor responds; E2/EE means unsupported |
| 2.2 | F6, C6 | 35 tracks the command; stop works |
| 2.3 | FB/FD (3 modes), CB/CD, 5–10° | 36 reaches the target, 37 ≈ 0, no stall |
| 2.4 | command above the current limit | `UnsupportedByProfile`, nothing sent |
| 2.5 | F1/FC | `UnsupportedByProfile` on FW 105 |
| 2.6 | 9A homing (only if mechanically safe), 9C | 3B flags change |
| 2.7 | stall by hand at 100 mA, then 0E 52 | the stall-protection flag sets, then clears |
| 2.8 | sync plus trigger on 2 motors; AA | both start within about 1 ms |

### R3: persistent or link config

Spare motor only. Use save=0 first, and power-cycle to revert.

- Response mode change (then 02/9F/E2 replies are visible).
- Checksum XOR and CRC-8 end to end.
- Parameter opcodes, one at a time, verified through 42.
- save=1, address and bitrate writes: **never on the working pair.**

### R4: board-level fault injection

| # | Test | Pass criterion |
| --- | --- | --- |
| 4.1 | `bitrate 500k` with the motors at 1M, then send reads | BusOff, requests fail without hanging; `bitrate 1m` recovers and a read succeeds |
| 4.2 | unplug CAN or power off the motors | same as 4.1 |
| 4.3 | error-passive | not observable today; needs `can stat` |
| 4.4 | queue full, Expired, Partial | `can stress` during 4.1 |
| 4.5 | bitrate switch while streaming, then reboot | the start sweep turns the streams off (done 2026-11-08) |

## Suspected defects, from reading the source

1. **Spurious job failure (confirmed in source).**
   - `Core.cpp:106` records the transport's global `txFailures` at submit, and
     `Core.cpp:154` fails the job if that number has changed when it is dispatched.
   - `Esp32TwaiTransport.cpp:131` adds the SDK's cumulative `tx_failed_count`.
   - So an asynchronous wire failure of *any* earlier frame fails every job queued
     behind it, including other motors' jobs. Each of those is then quarantined
     (`Driver.cpp:404-405`).
2. **No bus-off recovery, error-passive state, error counters or TWAI alerts**
   (`Core.h:9,11`, `Esp32TwaiTransport.cpp:75-82`). The apps say "reboot to recover".
3. **Transport counters can go backwards** after a reinstall
   (`Esp32TwaiTransport.cpp:130-133,187`). This is harmless only because the Bus is
   rebuilt.
4. **The BSP allows only 500k and 1M** (`Board.h:154`), while the codec knows 10 rates.
5. **Completion replies are never tied to a request.** A later 9F counts as unsolicited
   or can match a later request with the same opcode (`Driver.cpp:450-453,469-472`). The
   ResponseMode byte has no enum.
6. **Undecoded reads:** 38 is accepted for timed return but not decoded, and 13, 16, 20–23,
   3F, 41 and 49 are also not decoded (`Driver.cpp:189`, `Telemetry.cpp:70`).
7. **Series nibble:** HW 0x230A decodes as series 2, but `Telemetry.h:13` documents 0=X,
   1=Y.
8. **Broadcast:** `expectReply` is ignored, and motor 1's reply to AA arrives as
   unsolicited and could match a new request (`Broadcast.cpp:231-245`).
9. **Aux pins can never validate:** 3 and 46 are strapping pins (`Board.h:88,161`).
