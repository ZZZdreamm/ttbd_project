"""`mise run verify-destroyed`: confirm nothing from the exercise is left running or billing."""

from __future__ import annotations

from typing import Protocol

from tbd_lakehouse.config import Settings, load_settings

LAB_WAREHOUSES = {"WH_TRANSFORM", "WH_QUERY"}


class GcpProbe(Protocol):
    def project_state(self, project_id: str) -> str | None: ...  # None = not found
    def billing_linked_projects(self, billing_account: str) -> list[str]: ...


class SfProbe(Protocol):
    def warehouses(self) -> set[str]: ...
    def database_exists(self, name: str) -> bool: ...
    def pipeline_objects(self) -> list[str]: ...


def check(gcp: GcpProbe, sf: SfProbe, settings: Settings) -> list[str]:
    problems = []
    for pid in (settings.mgmt_project_id, settings.data_project_id):
        state = gcp.project_state(pid)
        if state not in (None, "DELETE_REQUESTED"):
            problems.append(f"GCP project {pid} is {state} (expected deleted)")
    linked = [p for p in gcp.billing_linked_projects(settings.billing_account)
              if p in (settings.mgmt_project_id, settings.data_project_id)]
    if linked:
        problems.append(f"billing account {settings.billing_account} still linked to {', '.join(linked)}")
    for wh in sorted(sf.warehouses() & LAB_WAREHOUSES):
        problems.append(f"Snowflake warehouse {wh} still exists")
    if sf.database_exists("LAKEHOUSE"):
        problems.append("Snowflake database LAKEHOUSE still exists")
    problems += [f"Snowflake {o} still exists" for o in sf.pipeline_objects()]
    return problems


class _Gcp:
    def __init__(self):
        from google.cloud import billing_v1, resourcemanager_v3

        self._rm = resourcemanager_v3.ProjectsClient()
        self._billing = billing_v1.CloudBillingClient()

    def project_state(self, project_id):
        from google.api_core import exceptions

        try:
            return self._rm.get_project(name=f"projects/{project_id}").state.name
        except (exceptions.NotFound, exceptions.PermissionDenied):
            return None

    def billing_linked_projects(self, billing_account):
        infos = self._billing.list_project_billing_info(name=f"billingAccounts/{billing_account}")
        return [i.project_id for i in infos if i.billing_enabled]


class _Sf:
    def __init__(self):
        from tbd_lakehouse.sf import connect

        self._c = connect("ACCOUNTADMIN", warehouse=None)

    def _show(self, sql):
        cur = self._c.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def warehouses(self):
        return {r["name"] for r in self._show("SHOW WAREHOUSES")}

    def database_exists(self, name):
        return bool(self._show(f"SHOW DATABASES LIKE '{name}'"))

    def pipeline_objects(self):
        out = []
        for kind in ("PIPES", "TASKS", "DYNAMIC TABLES"):
            for r in self._show(f"SHOW {kind} IN ACCOUNT"):
                if r.get("database_name") not in ("SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA"):
                    out.append(f"{kind[:-1]} {r['database_name']}.{r['schema_name']}.{r['name']}")
        return out


def main() -> int:
    settings = load_settings()
    problems = check(_Gcp(), _Sf(), settings)
    if problems:
        print("Not clean yet:\n" + "\n".join(f"  - {p}" for p in problems))
        return 1
    print("All clean. GCP projects are pending deletion (Google purges them after 30 days; their IDs stay "
          "reserved until then). The Snowflake trial account expires on its own.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
