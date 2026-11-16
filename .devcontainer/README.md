# Codespace (Linux, strict mode)

With Docker Desktop on your own PC, `uv run python scripts/check_linux.py` does the same check
in a local container built from this image with these settings, without using codespace hours.
The codespace stays useful when the PC is busy or off, or for working inside Linux.

Tracefix's strict isolation (bubblewrap) only runs on Linux. This codespace is a Linux machine
set up like Linux CI, so the Linux tests can run here before a push instead of on CI minutes.

- Create it: GitHub → Code → Codespaces → "Create codespace on <branch>" (2-core is enough;
  4-core runs the suite faster but uses the monthly quota twice as fast).
- The first start installs bubblewrap, uv and the project, then prints the isolation level. It
  should say `strict`.
- Run what Linux CI runs:
  `uv run python scripts/check.py`
  (`TRACEFIX_REQUIRE_STRICT=1` is set, so a silent fall back to basic isolation fails the tests.)
- Stop the codespace when done (it also stops itself after 30 idle minutes): its hours count
  against the monthly quota.

If strict mode isn't available, the setup says so. The container settings in
`devcontainer.json` (`SYS_ADMIN`; unconfined seccomp, AppArmor and system paths) are what let
bubblewrap make its namespaces and mount a fresh `/proc`. A setting change needs a rebuild:
Ctrl+Shift+P → "Codespaces: Rebuild Container".
