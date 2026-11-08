# Notes for agents working in this workspace

- Start with `README.md` (package map, status, workflow) and
  `docs/joint-control-requirements.md` (what the joint controller must do, what is agreed
  and what is only proposed, roadmap, open questions) and `docs/hardware-coverage.md` (the current phase: what has been proven on hardware, and the test plan). Update those documents when a
  requirement changes or a question is answered.
- Packages are submodules under `repos/`, and each is its own repository. Branch and
  commit inside the submodule, then bump the pointer here.
- Hardware rules:
  - Never enable or energize a motor, or raise current, speed or voltage limits, without
    the owner's explicit agreement for that test.
  - Never commit or print Wi-Fi credentials. The `wifi` command is serial-only.
- On Windows, git is not on the bash PATH: use PowerShell `git -C <path>`. Pass commit
  messages and PR bodies through files (`git commit -F`, `gh pr create --body-file`).
  PowerShell 5.1 mangles embedded quotes.
- Device web pages: after changing one, load it in real Chrome over DevTools against the
  board and read the rendered values. A syntax check is not enough.
