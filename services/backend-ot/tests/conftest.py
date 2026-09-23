"""
Root test configuration shared by unit and integration tests.

Status-first verbose output: `pytest -v` prints each test as

    PASSED  [ 33%] tests/unit/helpers/modbus/test_modbus_data_mapping.py::...::test_x

instead of pytest's default `tests/...::test_x PASSED [ 33%]`, so outcomes line up in a
column at the start of the line. It swaps pytest's terminal reporter for a subclass that
changes only the verbose per-test line; everything else (summaries, tracebacks, colors) is
pytest's own. It leans on pytest internals (`_pytest.terminal`), so if an upgrade breaks
the import or the reporter isn't the stock one, it quietly keeps pytest's default output.
"""

import sys

import pytest

try:
    from _pytest.terminal import TerminalReporter, _get_raw_skip_reason
except ImportError:  # pytest internals moved: fall back to the default reporter
    TerminalReporter = None


def _outcome_markup(report: pytest.TestReport) -> dict[str, bool]:
    """Same colors pytest uses: green pass, yellow xfail/skip, red fail."""
    if report.passed:
        return {"yellow": True} if hasattr(report, "wasxfail") else {"green": True}
    if report.failed:
        return {"red": True}
    if report.skipped:
        return {"yellow": True}
    return {}


if TerminalReporter is not None:

    class StatusFirstReporter(TerminalReporter):
        def _status_first(self) -> bool:
            return self.config.get_verbosity(pytest.Config.VERBOSITY_TEST_CASES) > 0

        def pytest_runtest_logstart(self, nodeid, location) -> None:
            # Default verbose mode prints the test id before it runs; we print the whole
            # line once the outcome is known instead.
            if not self._status_first():
                super().pytest_runtest_logstart(nodeid, location)

        def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
            if not self._status_first() or hasattr(report, "node"):  # quiet mode / xdist
                super().pytest_runtest_logreport(report)
                return

            self._tests_ran = True
            category, letter, word = self.config.hook.pytest_report_teststatus(
                report=report, config=self.config
            )
            markup = None
            if isinstance(word, tuple):
                word, markup = word
            self._add_stats(category, [report])
            if not letter and not word:  # a passing setup/teardown phase
                return

            self._progress_nodeids_reported.add(report.nodeid)
            self.ensure_newline()
            self._tw.write(f"{word:<8}", **(markup or _outcome_markup(report)))
            if self._show_progress_info:
                progress = self._get_progress_information_message().strip()
                self._tw.write(f"{progress} ", cyan=True)
            self._tw.write(self._locationline(report.nodeid, *report.location).rstrip())
            if report.skipped or hasattr(report, "wasxfail"):
                reason = _get_raw_skip_reason(report)
                if reason:
                    self._tw.write(f" ({reason})")
            self.currentfspath = -2  # line is complete; don't append a file-path prefix
            self.flush()


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    if TerminalReporter is None:
        return
    default_reporter = config.pluginmanager.getplugin("terminalreporter")
    if type(default_reporter) is not TerminalReporter:  # absent, or already customized
        return
    config.pluginmanager.unregister(default_reporter)
    config.pluginmanager.register(StatusFirstReporter(config, sys.stdout), "terminalreporter")
