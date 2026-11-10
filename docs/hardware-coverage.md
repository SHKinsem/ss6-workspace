# Hardware test coverage

This is the current phase: a demo that exercises the SS6 board, the CAN library and the
ZDT motors as completely as possible on real hardware. This file tracks what has been
proven on hardware and what has not, and the planned test order. Update the "Verified"
column as tests pass, with the date and any evidence.

- First compiled on 2026-11-08 from a source inventory. Line references are in
  `repos/<pkg>/src/...` at that date.
- Bench: two ZDT X42S motors (HW 0x230A, ids 1 and 2) on the intermediate board,
  1 Mbit/s, about 19 V (43 reads 19.1 and 19.3 V), unloaded and fixed. Firmware: id1
  FW_Ver 207 (V2.0.7, upgraded 2026-11-09 from 105), id2 FW_Ver 107 (read 2026-11-09; earlier notes said 105 for both).
- Both motors come out of power-up **enabled** (3A = 0x03). The start-up sweep disables
  them, as designed.

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

## Verified 2026-11-09 (over Wi-Fi, ss6-control)

All tests ran through `POST /api/cmd`, `/api/log` and `/api/samples`, with no USB.

- **R0, done except 0.3:**
  - **0.1:** `1A` replies with 2 data bytes (id1 `00 04`, id2 `00 24`).
  - **0.2:** 39 reads `00 1B` (+27 °C) on both motors, and the 43 temperature bytes agree
    (`00 1B`).
  - **0.4:** HW 0x230A (type 3) on both; FW 105 and 107.
  - **0.5:** 13, 16, 20–24, 26, 27, 32–34, 37, 3B–3D, 3F, 41 and 49 all reply with the
    lengths in `Codec::responseLength`. 21, 22 and 49 arrive as 3 frames and 42/43 as 5,
    the same on both motors. **38 is not supported:** both motors answer `00 EE 6B`.
  - **0.6:** 24, 26, 27, 32–34, 37, 39 and 3A–3D stream at 5 and 10 ms with intervals
    within about 0.17 ms and no missing frames (`stream capture`). **A 38 stream is
    acknowledged but sends nothing.**
  - **0.7 (wire level, raw path):** under a 1 ms 36 stream, 8 of 8 multi-frame replies
    (42 and 43) arrived as 5 contiguous frames: the motor finishes the reply before the
    next sample. Driver reassembly under a stream is still untested.
  - **0.8:** two 1 ms streams plus 40 raw reads over 10.6 s: 1000.4 frames/s per motor,
    rx missed 0, overrun 0, arb lost 0.
- **Bus errors:** TWAI `bus_error_count` rises with traffic, about 1 per 175 frames
  (120 in 10.6 s at 2000 frames/s). It stays 0 when the bus is quiet, with arb lost 0.
  One `txFailures` was seen during a 500 Hz control run. **Check the physical layer:**
  termination (120 Ω at each end) and wiring.
- **R1:**
  - **1.1:** FE on a disabled motor: id1 answers `FE E2` (refused), and `9C` answers 02.
    **id2 (FW 107) does not answer FE or 9C at all.**
  - **1.2:** the motor does not range-check the F3 enable byte: `F3 AB 02 00` was accepted
    (02) and **enabled** id1. The driver refuses values above 1, so only the raw path is
    exposed.
- **ss6-control on id1, 200 Hz, 150 mA, 20 rpm:** see "Control findings" below.

## Verified 2026-11-09, afternoon: zdt_x::Motor on ss6::CanTask (ss6_motion firmware)

- **Driver-side loops, current-capped:**
  - `CD` (3 frames) and `C6` (2 frames) are the first multi-frame TX on hardware, with
    0 TX failures.
  - At a 20 mA cap a +10° move went 0.2°, so the cap holds.
- **Both motors at 500 Hz, under Wi-Fi and HTTP polling every 50 ms:**
  - The CAN task ran 8693 cycles: period 1.46–2.52 ms (mean 2.000), 0 late, work at most
    1.15 ms.
  - Feedback: about 8160 samples per motor, max gap 4 ms; 0 status misses, 0 TX failures.
  - ±30° moves end within 0.02°. Velocity ±5 rpm measures +4.94 / −5.07 rpm (sd 0.3–0.5).
  - `stop()` ends in a position hold.
- **Response mode:** id2 (FW 107) has config `ResponseMode` 0 and answers no control
  command, so FE, 9C and CD timed out. `Motor` reads 42 at start-up and does not wait for
  replies on such a motor. id2's closed-loop current is 5000 mA (id1: 1600 mA), so
  enable ends with a capped `CD` hold.
- **Single-shot TX loses frames.** With TWAI single-shot (no retransmission), 6 TX
  failures in 2.5 s next to two 500 Hz streams faulted id1 on missed status reads.
  `CanTask` now enables ordinary retransmission.
- **Termination:**
  - Before the second resistor was soldered on: 685 bus errors in 17 s, about 1 per 24
    frames.
  - After it (CAN_H–CAN_L now 60 Ω): 76 in 17 s, about 1 per 220.
  - With one 500 Hz stream: 13 in 10 s. With two: 34 in 10 s.
  - TEC and REC stay 0, and retransmission absorbs the errors.
  - The error type is not observable: the IDF ISR clears the error code capture register,
    which reads 0. **Open:** scope the bus, or try other 1 Mbit/s bit timings (sample
    point, SJW).

## Control findings (2026-11-09, id1, unloaded)

- **The old default gains (kp 50, kd 5) are far too high.** The owner found by hand that
  kp 2 is already large, with ki and kd very small. The defaults are now kp 2, ki 0, kd 0.
- **Static friction:** about 30 mA (forward) to 55–80 mA (backward) to break away.
  **Kinetic friction:** about 45 mA forward and 55 mA backward, measured as the mean
  current during a 5 deg/s ramp.
- **Stick-slip.** The rotor creeps, sticks, then slips several degrees in 5–10 ms.
  **The 20 rpm speed clamp drives it.** It zeroes the output at 20 rpm, the rotor stops
  and springs back toward a detent (about −5 rpm), and then the output must break static
  friction again. A position-dependent cogging table was not visible in this data: the
  places where it stuck are irregular, not 1.8° apart.
- **Speed estimate fix:** speeds are now computed from elapsed stream periods, not receipt
  times. Before, a burst after an HTTP stall read 5× high: a 183 rpm "overspeed" while the
  rotor moved under 2° in 50 ms.
- **0x31 feedback** (16-bit, unwrapped, anchored to 36 at arming) holds within 0.01° and
  agrees with 36.
- **Results** (±30° at 5 deg/s, tracking error mean / sd / max, forward):

  | Run | Error mean / sd / max (deg) |
  | --- | --- |
  | kp 2 ki 5 kd 0.5 | +3.2 / 4.1 / 12.6 |
  | plus ff 45 mA | +0.7 / 2.7 / 6.3 (end error −5.5 → −0.2) |
  | plus kd 2 | +0.9 / 2.5 / 6.5 (reverse peak 85.7 → 72.5 rpm) |
  | at 500 Hz | sd 2.1–2.4, no real gain, and it ended in a `torque not acknowledged (TimedOut)` fault after one TX failure |

- **Open:**
  - make the speed clamp limit the output to the feed-forward level instead of zeroing
    it (needs the owner's agreement);
  - test the motor's own position loop with a current cap (CB/CD, multi-frame TX) as an
    alternative for slow, smooth motion.

## Firmware upgrade (2026-11-09)

Motor id1 was upgraded from FW 105 to FW 207 (V2.0.7) with ZDT's own tool,
`Y42_IAP_260805.exe`, through the ESP32 board acting as a gs_usb USB-to-CAN bridge. It took
40,231 data frames in about 10 minutes, with no TX failures and no bus-off. The motor kept its
config. id2 was then FW 107 (it went to FW 207 over native IAP later the same day, see
below). The tests above this section were run before the upgrade, on FW 105.

- Protocol notes from the capture: `repos/zdt-x-driver/docs/firmware-upgrade.md`.
- The bridge, its design and its hardware results: `repos/ss6-bsp/docs/usb-can-bridge.md`.

Deferred, not started: keeping the bridge in a factory partition and switching modes with
a command instead of a reflash. Tracked in
[ss6-control#7](https://github.com/SHKinsem/ss6-control/issues/7).

V2.0.x changelog items that matter to us (vendor file `ZDT_X42S固件更新记录_260928.txt`):

- V2.0.0: fast position F1/FC, and a fix for the multi-motor command ack.
- V2.0.2: X firmware with acceleration 0 updates the speed immediately.
- V2.0.3: fixes a motor hang when the CAN timed return runs at a high rate together with
  high-frequency commands.
- V2.0.5: much stiffer X firmware, with the `X_Stiff` menu.
- V2.0.6: the screen shows the firmware type and version.

### Native Wi-Fi IAP verified, 2026-11-09 21:50–21:52 HKT

Owner-approved native run: ESP32 `/iap`, address 1, 1 Mbit/s,
X42S HW0x230A, reinstalled FW207 using the same vendor image. id2 was not upgraded.

- Image: 160,923 bytes, SHA256
  `94de45ddf87ba3587887779196a85f8b124cbcba46a705a3edb0a92f9f9fc1a5`.
- **Succeeded in 86.961 s** as observed by HTTP polling; data phase 85.334018 s.
  40,231 distinct frames, 40,235 TX submissions, 40,234 data ACKs. One restart
  after sequence 3 was not acknowledged, consistent with the earlier PC-tool run.
- Captured **80,479 entries, 0 dropped**. All data payloads, including final FF
  padding, match the vendor file byte-for-byte. TX records are software queue
  submissions, not electrical wire timestamps; RX times are CAN-task observations.
- Final wire replies: `F3 02 6B`, `3A 02 6B` (disabled),
  `1F 00 CF 23 0A 6B` (FW207/HW0x230A).
- 0 TX failures, 0 RX missed/overruns, TEC/REC 0; **131 bus errors** were counted
  and absorbed by retransmission. This does not resolve the physical-layer issue.
  The error-code sampler cannot identify their true type (ISR clears ECC).
- After release and fresh startup reads: id1 Disabled, FW207, response mode 1,
  closed-loop 1600 mA; id2 Disabled, FW107, response mode 0, closed-loop 5000 mA.
  These observed config fields are unchanged; a complete 32-byte config or position
  preservation comparison was not performed.
- Live rejection checks: unauthenticated start 401; truncated image 400; no IAP
  frames sent. Full image upload hash matched the source before starting.
- Real board page visually verified in Edge (Chromium): progressing at 20.9%, then
  successful at 100%. Chrome-specific validation remains unperformed. A stale
  upload-only message found in this check was removed from active/result display.

Evidence: local workspace `logs/iap-20261109-native/`, archived in the private
ss6-control repository under `evidence/iap-20261109-native/` (`result.json`, `progress.jsonl`,
`can-capture.csv`, `capture-analysis.json`, pre/post console and status snapshots,
upload, rejection-test and deployment records; raw CSV is gzip-compressed in Git).
AP password text is redacted. The public workspace contains only a sanitized summary
under `docs/evidence/iap-20261109-native/`, not raw firmware-bearing capture frames.
The host helper is `tools/iap_acceptance.py`; capture download is only allowed after
an attempt ends. Power-loss and deliberate bootloader recovery are not yet
separately accepted.

### Native Wi-Fi IAP on address 2, FW107 -> FW206 -> FW207, 2026-11-09 23:25–23:51 HKT

Owner-approved runs, with the multi-address / multi-image code: ss6-control `/iap`
(address selection, full-SHA256 catalog of X42S default-X V2.0.1–V2.0.7). The firmware
went to the board over USB with esptool, flash hash checked. Before the runs: id1
Disabled/FW207, id2 Disabled/FW107.

1. **FW107 -> FW206: data complete, automatic check failed.** Image 160,568 bytes,
   SHA256 `c869bc59ee9a71665ab1adfa71bc494244b8e8c2be488fd0ced4be70b56bbdb2`.
   All 40,142 frames ACKed on `0x2DD`, with the count field `9C CE` = 40,142 (so it is
   the frame count, not a constant). One restart. Captured 80,329 entries, 0 dropped;
   all payloads match the image. 157 recoverable bus errors, 0 TX failures, 0 RX loss.
   After the reboot the motor did not answer on CAN: the post-upgrade check timed out
   and id2 read Offline after release. The owner then reset the communication setting
   on the motor itself, and the next startup read id2 Disabled/FW206, response mode 0,
   closed-loop 5000 mA. V2.0.1 added the P_Serial selection, so V1.x -> V2.x likely
   resets it; that is a likely cause, not a proven one. This run is a successful
   transfer that needed a manual fix, not an automatic success.
2. **FW206 -> FW207: succeeded.** Image 160,923 bytes, SHA256
   `94de45ddf87ba3587887779196a85f8b124cbcba46a705a3edb0a92f9f9fc1a5`. 40,231 frames
   ACKed, one restart, 80,478 entries captured, 0 dropped; FW207 and Disabled checked
   over CAN by the engine. HTTP polling dropped out at times, so the poll timestamps do
   not measure the transfer time.
3. **After the owner rebooted the controller (2026-11-10 00:04):** id1 Disabled/FW207,
   response mode 1, 1600 mA; id2 Disabled/FW207, response mode 0, 5000 mA. IAP idle and
   unlocked. id1 was untouched by both runs, so address targeting works.

Not covered:

- Only 6,400 of the 80,478 FW207 capture entries were downloaded before the network
  dropped; the controller reboot cleared the rest. FW207's payloads were not compared
  in full. FW206 has a complete capture.
- FW201–FW205 have not been flashed. Being in the catalog is not acceptance.
- Wi-Fi was unreliable during the session (HTTP timeouts while serial reported the
  station connected). Not diagnosed. A likely cause was found on 2026-11-10: on an SSID
  served by several access points, the Arduino fast scan joined the first access point
  on channel 1. The board then reported "connected" at an address the laptop could not
  ping, and old and new firmware alike showed this. Joining the strongest access point
  fixed it on the bench ([ss6-bsp#6](https://github.com/SHKinsem/ss6-bsp/pull/6)). That
  network was a different one, so this does not prove the 11-09 timeouts had the same
  cause.
- The page's hint about P_Serial/CAN, shown when every frame was ACKed but the check
  failed, was added after these runs. It has not been checked on the board, nor has
  the page in Chrome (Edge only).
- No power-loss, interrupted-transfer or bootloader-recovery test.

Evidence: private ss6-control `evidence/iap-20261109-multi-motor/` (deployment,
per-run status/console snapshots, progress, results, gzip raw captures). Public
summary: `docs/evidence/iap-20261109-multi-motor/acceptance-summary.json`.

## STEP/DIR on two motors (2026-11-10, ss6-tcode)

Setup: id1 and id2, FW207, unloaded. The drive mode is `tc drive stepdir`: FastAccelStepper
on the RMT, 16 microsteps, with id2 mirroring id1. Motor config was written session-only at
1500 mA closed loop, 1200 mA stall and 1000 rpm, all approved by the owner.

- **id1 and id2 move together on +90/−180/+90°.** Both return to within 0.03°.
- **Swapped cables were caught by the follow-error guard, but only after enabling.**
  - id2's pulses reached id1, which was disabled, so it counted −202 pulses on 0x32 and did
    not move.
  - Auto-detection of connector and direction is
    [ss6-tcode#2](https://github.com/SHKinsem/ss6-tcode/issues/2).
- **Both motors need `tc dirinv` on the current wiring.** It is a toggle, and it resets at
  boot.
- **The command lease is 3 s.** A host must stream input (`tc send`, or a UDP `X`) at least
  once a second while a motor is enabled. Otherwise the motor faults with "command lease
  expired".
- **Funscript results:**

  | Span | Result | Error rms | id2−id1 rms | Lag |
  |---|---|---|---|---|
  | 20° | ok | 2.4° | 0.75° | 74 ms |
  | 100° | ok | 12° | 3.7° | 70 ms |
  | 500°, follow-error limit 20° | both stopped at 5.6 s | — | — | — |
  | 500°, follow-error limit 360° | ok, but the motors reach only 294 of the 763 rpm asked | 68° | 3.75° | 78 ms |

- **The lag is inside the motor.**
  - TCode to stepper target is 4 ms, and target to the RMT pulses is another 4 ms.
  - Pulses to the motor's position is **64 ms**.
  - Turning interpolation off (`m 1 cfg set interp 0`) did not change it.
  - PID (0x21, through `m <id> read 21`) reads `126640 126640 15600 26` on both motors.
    Which value is which is not verified.
- **STEP/DIR is noticeably quieter than CAN position streaming**, by the owner's ear.
- **Wi-Fi.** At a site with 22 access points, the all-channel join scan took 7.6 s, and the
  4 s join grace treated "ssid not found" as final. The fix is
  [ss6-bsp#7](https://github.com/SHKinsem/ss6-bsp/pull/7), with a 12 s grace. Afterwards the
  laptop could reach the board only once over that router (not diagnosed), so the bench ran
  over USB.
- **Open:**
  - The PID field meanings and how PID is written.
  - Whether a higher position Kp shortens the 64 ms lag.
  - The follow-error limit at large spans.

## Coverage matrix

### ss6-bsp

| Feature | Verified | How to test | Risk |
| --- | --- | --- | --- |
| CAN TX7/RX6, 1M/500k, run-time switch | Yes | — | R0 |
| Transport status: Running and counters | Partly. BusOff, Recovering and Stopped not seen | R4-1 | R0/R4 |
| Transport errors (`TransmitFailed`, `NotRunning`) | Partly | R4 tests | R4 |
| `txReadiness` Busy deferral, single-shot | Partly. TX is low rate | multi-frame TX plus `can stress` | R2/R4 |
| Bus-off recovery | No. There is no API, only close + configure + start | R4-1 | R4 |
| STEP/DIR ×6 (5/4, 16/15, 18/17, 38/37, 40/39, 42/41) | Slots 1–2 yes (2026-11-10, two motors, ss6-tcode); 3, 5, 6 no | new `pins` command, scope on a bare connector | R1 |
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
  - ss6-probe: `scan`, `read`, `watch`, `trace`, `bus`, `bitrate`. ss6-probe was retired
    on 2026-11-09; these are to return as ss6-control debug commands.
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
10. **38 is treated as a timed-return info opcode (confirmed on hardware, 2026-11-09).**
    `Codec::timedReturnInfoOpcode` accepts it, but FW 105 and 107 answer a 38 read with
    `00 EE 6B`, and a 38 stream is acknowledged and then sends nothing. A caller gets
    `ReplyObserved` for a stream that never produces samples.
