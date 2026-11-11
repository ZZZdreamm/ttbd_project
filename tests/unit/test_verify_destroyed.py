from tbd_lakehouse.config import load_settings
from tbd_lakehouse.ops.verify_destroyed import check

ENV = {"TF_VAR_semester": "2026z", "TF_VAR_team_id": "07", "TF_VAR_billing_account": "01AB",
       "TF_VAR_notification_email": "a@b.pl", "SNOWFLAKE_ACCOUNT": "MYORG-TBD07"}


class FakeGcp:
    def __init__(self, states=None, linked=()):
        self.states, self.linked = states or {}, list(linked)

    def project_state(self, project_id):
        return self.states.get(project_id)

    def billing_linked_projects(self, billing_account):
        return self.linked


class FakeSf:
    def __init__(self, warehouses=(), db=False, objects=()):
        self._w, self._db, self._o = set(warehouses), db, list(objects)

    def warehouses(self):
        return self._w

    def database_exists(self, name):
        return self._db

    def pipeline_objects(self):
        return self._o


S = load_settings(ENV)
GONE = {"tbd-2026z-stud07-mgmt": "DELETE_REQUESTED", "tbd-2026z-stud07-data": None}


def test_clean_when_projects_pending_deletion_and_no_sf_objects():
    assert check(FakeGcp(GONE), FakeSf(warehouses={"COMPUTE_WH"}), S) == []


def test_reports_active_project():
    problems = check(FakeGcp({**GONE, "tbd-2026z-stud07-data": "ACTIVE"}), FakeSf(), S)
    assert any("tbd-2026z-stud07-data" in p and "ACTIVE" in p for p in problems)


def test_reports_leftover_warehouse():
    problems = check(FakeGcp(GONE), FakeSf(warehouses={"WH_TRANSFORM", "COMPUTE_WH"}), S)
    assert any("WH_TRANSFORM" in p for p in problems) and not any("COMPUTE_WH" in p for p in problems)


def test_reports_billing_still_linked():
    problems = check(FakeGcp(GONE, linked=["tbd-2026z-stud07-data"]), FakeSf(), S)
    assert any("billing" in p.lower() for p in problems)


def test_reports_database_and_pipeline_objects():
    problems = check(FakeGcp(GONE), FakeSf(db=True, objects=["PIPE X.Y.Z"]), S)
    assert any("LAKEHOUSE" in p for p in problems) and any("PIPE X.Y.Z" in p for p in problems)
