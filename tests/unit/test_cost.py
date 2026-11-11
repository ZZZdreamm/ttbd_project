import pytest

from tbd_lakehouse.ops.cost import format_summary, summarize


def test_cost_summary_splits_and_converts():
    s = summarize([{"SERVICE_TYPE": "WAREHOUSE_METERING", "CREDITS_USED": 3.0},
                   {"SERVICE_TYPE": "PIPE", "CREDITS_USED": 0.5},
                   {"SERVICE_TYPE": "SNOWPIPE_STREAMING", "CREDITS_USED": 0.5}])
    assert (s.warehouse_credits, s.serverless_credits) == (3.0, 1.0)
    assert s.credits_used == 4.0
    assert s.usd == pytest.approx(15.6) and s.pct_of_cap == pytest.approx(33.33, 0.01)


def test_empty_usage_is_zero():
    s = summarize([])
    assert (s.credits_used, s.usd, s.pct_of_cap) == (0, 0, 0)


def test_format_warns_near_cap():
    text = format_summary(summarize([{"SERVICE_TYPE": "WAREHOUSE_METERING", "CREDITS_USED": 11.0}]))
    assert "11.00 of 12 credits" in text and "WARNING" in text and "3 h" in text
    assert "WARNING" not in format_summary(summarize([{"SERVICE_TYPE": "WAREHOUSE_METERING", "CREDITS_USED": 1.0}]))
