# Native motor firmware upgrade: checkpoint and completion plan

## Owner direction (2026-11-09)

Make Wi-Fi motor firmware upgrade a complete supported feature, not a one-image bench
utility. First record and push the working implementation and acceptance evidence.
The checklist below is the proposed implementation/acceptance plan; protocol hypotheses
must be verified before broadening supported hardware, addresses or firmware files.

## Working checkpoint

- `zdt_x::Iap`: nonblocking stop-and-wait engine on the existing CAN owner, fresh normal
  preflight, 500 ms ACK timeout, bounded full restart, post-boot disable and version read.
- ss6-control `/iap`: PSRAM upload, CRC32 integrity check and SHA256 display, explicit
  start, progress, maintenance lock, retry/abort/release, and bounded raw-frame capture.
- On 2026-11-09, id1 X42S HW0x230A reinstalled FW207 successfully in 86.961 s.
  All 40,231 distinct data payloads matched the vendor image. One restart after seq3;
  80,479 trace entries, no trace drops, TX failures or RX missed/overruns.
- 131 recoverable CAN bus errors remain a separate physical-layer issue. Their true
  type was not identified. Successful transfer is not proof of an error-free bus.
- After release: id1 Disabled/FW207/response mode 1/closed-loop 1600 mA;
  id2 Disabled/FW107/response mode 0/closed-loop 5000 mA.
- 21 CTest tests and the simulation demo pass; the ESP32 firmware builds. Live page
  rendering was checked in Edge. Chrome-specific validation remains outstanding.
- Evidence: `logs/iap-20261109-native/`; deployed image hashes, upload hash, negative
  checks, timestamped progress, raw CSV, analysis and pre/post state/console logs.
  `TX_SUBMIT` is a software submission timestamp, not an electrical wire timestamp.
  Full evidence is archived in private `ss6-control/evidence/iap-20261109-native/`
  (raw CSV gzip-compressed). This public workspace publishes only a sanitized summary
  under `docs/evidence/iap-20261109-native/`.

## Current limits (do not present this as general support yet)

- Only address 1, 1 Mbit/s, HW0x230A, fixed-6B application replies, the captured
  160,923-byte X42S FW207 file and expected version 207.
- Size and the first 16 bytes are checked by the board; these do not authenticate an
  image. The bench helper additionally pins the complete SHA256 of the known image.
- `0x9D27` equals 40,231, the observed image's frame count. Whether this field is a
  count or constant is unresolved. Address-dependent `(address << 8) | 0xDD` is also
  still a hypothesis beyond address 1.
- Upload and trace are volatile. A reboot loses both; the next attempt replaces the
  trace. Capture download is currently an API/host-helper operation, not a page button.
- Cancel is not rollback and does not prove the motor disabled. Failed flash may
  leave the motor in bootloader; recovery requires a complete image and explicit action.
- Only the observed response mode/current fields were compared. Full configuration,
  position preservation, different target versions and deliberate power-loss recovery
  have not been accepted. This run was FW207 -> FW207, not a different-version upgrade.
- Device OTA password is reused. Finish product-facing authentication/authorization
  policy rather than relying on a development default or putting credentials in logs.

## Completion checklist, in recommended order

### 1. Establish a supported-image/protocol contract

- [ ] Resolve the first two payload bytes against another vendor image/capture.
- [ ] Verify address 2 targeting on an explicitly approved bench run; prove id1 is
  unaffected. Never infer broadcast upgrades from the current capture.
- [ ] Define metadata: family, compatible hardware, firmware type/version, byte size,
  full SHA256, source/provenance and permitted upgrade/recovery paths.
- [ ] Parameterize addressing, frame count, padding and expected post-upgrade version
  only after evidence. Bound image sizes, counters and sequence overflow explicitly.
- [ ] Reject mismatched/corrupt/unsupported images on the board before any flash frame;
  do not treat a filename, prefix or caller-provided CRC as vendor authenticity.

### 2. Finish lifecycle and recovery behavior

- [ ] Expose a coherent session model: uploading, staged, preflight, sending, rebooting,
  verifying, succeeded/failed/cancelled, released; eliminate stale messages/metadata.
- [ ] Separate observed pre-upgrade version from verified post-upgrade version.
- [ ] Read/compare the complete supported configuration before and after; define which
  fields may change across versions. Preserve evidence before releasing maintenance.
- [ ] Define and test cancellation during every phase, lost final ACK, restart limits,
  bus-off, task/device restart, interrupted HTTP upload and browser disconnect.
- [ ] Make failure/recovery status explicit, retain a useful last-result record across
  board reboot, and avoid silently discarding an unexported capture on retry.
- [ ] Verify that release/restart drops pending motion/enable requests and that every
  rejected/failed path preserves exclusive bus ownership and the intended control lock.
- [ ] Define recovery checks when normal hardware/version reads are unavailable.
  An offline motor is not automatically a compatible bootloader.

### 3. Complete the user interface

- [ ] Motor selection with current hardware/version/state, eligible-image information,
  upload progress, target confirmation, transfer progress, elapsed time and retries.
- [ ] Distinct data-complete vs verified-success states; actionable failure reasons and
  recovery/release choices; safe behavior after page reconnect or concurrent clients.
- [ ] Download result + raw log directly from the page; show trace overflow and make
  clear that submission/receive timestamps do not measure wire ACK latency.
- [ ] Coherent Chinese-facing messages, mobile layout and accessible state updates.
- [ ] Authentication appropriate for deployment, no browser persistence or logging of
  credentials, and separation from ordinary unauthenticated console actions as needed.

### 4. Acceptance before calling it complete

- [ ] Host protocol tests for variable metadata, frame boundaries, malformed/late ACKs,
  retries, all terminal paths and timer rollover.
- [ ] HTTP/integration tests for wrong/missing auth, multi-file/empty/truncated/oversized
  bodies, CRC/hash mismatch, disconnects, double start, competing upload and release.
- [ ] Real-browser interaction tests against the board, including upload and recovery
  UI (not just syntax checking or progress observed after API-driven start).
- [ ] Approved bench cases: distinct-version upgrade, another target address, recovery
  from interrupted transfer and power interruption with vendor recovery available.
- [ ] Record supply, hardware, initial/final versions and config, image hash, duration,
  transport counters and complete trace for every bench case.
- [ ] Merge dependencies first (driver, then application); after their commits are
  reachable from main, update workspace pointers and rerun the combined checks.

## Reproducing this checkpoint

Exact package commits and branch names are recorded in `docs/evidence/iap-20261109-native/source-checkpoint.json`.
The workspace gitlinks intentionally stay on already-merged commits until the feature
branches are merged, as required by the workspace workflow. For this checkpoint,
check out the manifest's driver, BSP and application revisions before building;
the unmodified workspace gitlinks alone do not include the native IAP implementation.

Do not publish the vendor firmware file or credentials with the source. The local
acceptance helper separates staging (`upload`) from actual flash (`run`). New movement,
power-loss and additional-device tests require the relevant owner authorization.
