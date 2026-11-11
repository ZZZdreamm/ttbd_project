import pytest

from tbd_lakehouse.config import load_settings
from tbd_lakehouse.sf import connect_kwargs

ENV = {"TF_VAR_semester": "2026z", "TF_VAR_team_id": "07", "TF_VAR_billing_account": "x",
       "TF_VAR_notification_email": "a@b.pl", "SNOWFLAKE_ACCOUNT": "MYORG-TBD07"}


def test_service_user_uses_key_pair(tmp_path):
    (tmp_path / "terraform_svc.p8").write_text("k")
    kw = connect_kwargs(load_settings(ENV), "ANALYST", secrets=tmp_path)
    assert kw["account"] == "MYORG-TBD07" and kw["user"] == "TERRAFORM_SVC"
    assert kw["authenticator"] == "SNOWFLAKE_JWT"
    assert kw["private_key_file"] == str(tmp_path / "terraform_svc.p8")
    assert kw["role"] == "ANALYST" and kw["warehouse"] == "WH_QUERY"


def test_ingest_user_uses_its_own_key(tmp_path):
    (tmp_path / "ingest_svc.p8").write_text("k")
    kw = connect_kwargs(load_settings(ENV), "INGEST", user="INGEST_SVC", secrets=tmp_path)
    assert kw["private_key_file"] == str(tmp_path / "ingest_svc.p8")


def test_demo_user_uses_pat(tmp_path):
    (tmp_path / "support_user.pat").write_text("tok123\n")
    kw = connect_kwargs(load_settings(ENV), "SUPPORT", user="SUPPORT_USER", secrets=tmp_path)
    assert kw["authenticator"] == "PROGRAMMATIC_ACCESS_TOKEN" and kw["token"] == "tok123"
    assert "private_key_file" not in kw


def test_missing_credential_names_the_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="support_user.pat"):
        connect_kwargs(load_settings(ENV), "SUPPORT", user="SUPPORT_USER", secrets=tmp_path)
