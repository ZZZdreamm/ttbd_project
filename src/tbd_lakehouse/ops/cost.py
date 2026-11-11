"""`mise run cost`: Snowflake credits used (warehouses + serverless) vs the cap."""

from __future__ import annotations

from dataclasses import dataclass

WAREHOUSE_TYPES = {"WAREHOUSE_METERING", "WAREHOUSE_METERING_READER"}
SQL = """
SELECT service_type, SUM(credits_used) AS credits_used
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE start_time >= DATEADD(day, -31, CURRENT_TIMESTAMP())
GROUP BY service_type
ORDER BY credits_used DESC
"""


@dataclass(frozen=True)
class CostSummary:
    credits_used: float
    warehouse_credits: float
    serverless_credits: float
    usd: float
    pct_of_cap: float
    cap: float = 12.0
    by_service: tuple[tuple[str, float], ...] = ()


def summarize(rows: list[dict], cap: float = 12.0, usd_per_credit: float = 3.90) -> CostSummary:
    by = tuple((r["SERVICE_TYPE"], float(r["CREDITS_USED"] or 0)) for r in rows)
    wh = sum(c for t, c in by if t in WAREHOUSE_TYPES)
    total = sum(c for _, c in by)
    return CostSummary(total, wh, total - wh, total * usd_per_credit, 100 * total / cap if cap else 0, cap, by)


def format_summary(s: CostSummary) -> str:
    lines = [f"Snowflake credits used (last 31 days): {s.credits_used:.2f} of {s.cap:g} credits "
             f"({s.pct_of_cap:.0f}%, ~${s.usd:.2f} at $3.90/credit)",
             f"  warehouses: {s.warehouse_credits:.2f}   serverless: {s.serverless_credits:.2f}"]
    lines += [f"    {t:<28} {c:.3f}" for t, c in s.by_service]
    if s.pct_of_cap >= 75:
        lines.append("WARNING: close to the cap. Run `mise run stop` when you are not working.")
    lines.append("Note: ACCOUNT_USAGE lags by up to ~3 h, so the latest usage may not show yet.")
    return "\n".join(lines)


def main() -> None:
    from tbd_lakehouse.sf import connect

    with connect("ACCOUNTADMIN") as c:
        cur = c.cursor()
        cur.execute(SQL)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    print(format_summary(summarize(rows)))


if __name__ == "__main__":
    main()
