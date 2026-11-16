# Security

Tracefix runs code it did not write: the project's tests, a pull request's changes and tests a
model wrote. Keeping that code away from your machine, your keys and the verdict is part of the
product, so a way around it is a security bug, and reports are welcome.

## Reporting a vulnerability

Report it privately: on the repository's **Security** tab, choose **Report a vulnerability**
(GitHub's private vulnerability reporting). Please do not open a public issue for it.

Say what you ran (the command or the workflow, the operating system, the isolation level the
receipt shows) and what happened. A small repository that shows it helps most.

Tracefix is pre-alpha and maintained by one person. You get an answer within a week, and credit
in the fix unless you prefer none. There is no bug bounty.

## Supported versions

Only the newest release, and `main` before the first release. Fixes are not back-ported.

## What counts

- Code under test **escaping strict isolation** (Linux with a working bubblewrap): writing outside the copy
  under test and its scratch folder, reaching the network, or reading the model key or the GitHub
  token.
- Code under test **changing a verdict** without being caught: getting past the tamper watch, or
  making one run influence another at strict isolation.
- The **GitHub Action** giving the model key or a write token to untrusted code: a fork's pull
  request treated as trusted, a `${{ }}` value reaching a shell, the reporting job running project
  code.
- A receipt (`receipt.md`, the PR comment, annotations) that **injects markup or links** from the
  issue, the code or test output.
- A secret written into a receipt, a log or an artifact, or a local path left unmasked in a
  receipt, the PR comment or an annotation.

## Known limits (documented, not vulnerabilities)

These are stated in [`docs/SPEC.md`](docs/SPEC.md) §4 and
[`docs/GITHUB_ACTION.md`](docs/GITHUB_ACTION.md); a report that shows one is worse than documented
is still welcome.

- **Basic isolation is not a sandbox.** Everywhere except Linux with a working bubblewrap, runs get a
  temporary copy, a clean environment, a timeout and a best-effort network block, and the receipt
  says so. Writes outside the watched folders are not detected. Verify untrusted code only at
  strict isolation (`--require-strict`); the Action refuses untrusted pull requests without it.
- **An escape from bubblewrap itself** (a kernel bug) is outside what Tracefix can stop: at strict
  isolation the verdict's integrity rests on the sandbox.
- **A test can lie about its own result.** It runs inside the pytest process and can patch it.
  Isolation stops damage, not lying; re-runs and cross-checks limit it.
- **The base branch's dependencies are trusted** as your own code.
- **Your code and the issue text are sent to Anthropic's API** with your key. Instructions hidden
  in them reach a model as data; a model only proposes, and every verdict comes from a run.
