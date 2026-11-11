from tests.live.report import CHECKS, exit_code, merge, render


def test_failing_test_makes_its_check_fail_with_short_message():
    results = merge([{"5 Masking": [["passed", ""], ["failed", "AssertionError: '***' != 'Jan'"]]}])
    table = render(results)
    row = next(line for line in table.splitlines() if "5 Masking" in line)
    assert "FAIL" in row and "'***' != 'Jan'" in row


def test_all_seven_rows_and_missing_check_is_not_run():
    table = render(merge([{"1 Infra": [["passed", ""]]}]))
    for c in CHECKS:
        assert c in table
    assert "NOT RUN" in next(l for l in table.splitlines() if "7 Guardrails" in l)


def test_exit_code_zero_only_when_every_check_passed():
    ok = {c: [["passed", ""]] for c in CHECKS}
    assert exit_code(merge([ok])) == 0
    assert exit_code(merge([{**ok, "4 Parity": [["failed", "x"]]}])) == 1
    assert exit_code(merge([{c: v for c, v in ok.items() if c != "4 Parity"}])) == 1


def test_merge_combines_parts():
    m = merge([{"5 Masking": [["passed", ""]]}, {"5 Masking": [["failed", "duckdb"]]}])
    assert len(m["5 Masking"]) == 2
