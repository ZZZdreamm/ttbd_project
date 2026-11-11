"""pytest plugin + CLI: one pass/fail row per exercise check.

Each pytest run (host, lab container) writes its results to .state/test-results-<part>.json via
--results-file; `python -m tests.live.report <files...>` merges them, prints the table and exits
non-zero unless every check passed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CHECKS = ["1 Infra", "2 Batch path", "3 Streaming path", "4 Parity", "5 Masking", "6 Tag propagation",
          "7 Guardrails"]


def merge(parts: list[dict]) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {c: [] for c in CHECKS}
    for part in parts:
        for check, results in part.items():
            out.setdefault(check, []).extend(results)
    return out


def _status(results: list[list[str]]) -> tuple[str, str]:
    if not results:
        return "NOT RUN", ""
    failed = [msg for outcome, msg in results if outcome != "passed"]
    if failed:
        return "FAIL", failed[0]
    return "PASS", f"{len(results)} test(s)"


def render(results: dict[str, list[list[str]]]) -> str:
    lines = ["", "Exercise checks", "=" * 78]
    for check in CHECKS:
        status, msg = _status(results.get(check, []))
        lines.append(f"{check:<20} {status:<8} {msg[:48]}")
    lines.append("=" * 78)
    return "\n".join(lines)


def exit_code(results: dict[str, list[list[str]]]) -> int:
    return 0 if all(_status(results.get(c, []))[0] == "PASS" for c in CHECKS) else 1


# ---------------------------------------------------------------- pytest plugin
def pytest_addoption(parser):
    parser.addoption("--results-file", default=None, help="write per-check results as JSON")


def pytest_configure(config):
    config._tbd_results = {}


import pytest  # noqa: E402


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        m = item.get_closest_marker("check")
        if m:
            msg = ""
            if rep.outcome != "passed":
                msg = str(getattr(rep, "longrepr", "") or "").strip().splitlines()[-1:] or [""]
                msg = f"{item.name}: {msg[0]}"
            item.config._tbd_results.setdefault(m.args[0], []).append([rep.outcome, msg])


def pytest_sessionfinish(session, exitstatus):
    path = session.config.getoption("--results-file")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(session.config._tbd_results))


def main(argv: list[str]) -> int:
    parts = []
    for p in argv:
        f = Path(p)
        parts.append(json.loads(f.read_text()) if f.exists() else {})
    results = merge(parts)
    print(render(results))
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
