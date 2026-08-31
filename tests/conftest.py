"""Fail the run on an unexplained skip.

WHY. On 2026-08-29 a class inserted above another silently adopted its @unittest.skipUnless
decorator; three new tests reported GREEN WITHOUT RUNNING. Separately, an @pytest.mark.asyncio
with the plugin absent made async tests inert. Both times the harness said "passed".

A skip count is a result, not a formality. A skip is allowed only if its reason names a tracked
issue, so "it's skipped for a reason" has to be an actual reason someone wrote down.
"""

import pytest

_ALLOWED = ("http://", "https://", "issue ")


def pytest_sessionfinish(session, exitstatus):  # noqa: ANN001
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    unexplained = [
        r for r in reporter.stats.get("skipped", [])
        if not any(tok in str(getattr(r, "longrepr", "")) for tok in _ALLOWED)
    ]
    if unexplained:
        reporter.write_line("")
        for r in unexplained:
            reporter.write_line(f"UNEXPLAINED SKIP: {r.nodeid}", red=True)
        reporter.write_line(
            f"{len(unexplained)} test(s) skipped without a tracked reason. "
            "A skip must name an issue URL, or it is a test that silently did not run.",
            red=True,
        )
        session.exitstatus = 1
