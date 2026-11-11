import pytest

from tbd_lakehouse.config import ConfigError, load_settings

BASE = {"TF_VAR_semester": "2026Z", "TF_VAR_team_id": "07",
        "TF_VAR_billing_account": "01ABCD-23EF45-6789AB",
        "TF_VAR_notification_email": "a@b.pl", "SNOWFLAKE_ACCOUNT": "myorg-tbd07"}


def test_project_ids_are_lowercase_and_named():
    s = load_settings(BASE)
    assert s.mgmt_project_id == "tbd-2026z-stud07-mgmt"
    assert s.data_project_id == "tbd-2026z-stud07-data"
    assert s.landing_bucket == "tbd-2026z-stud07-data-landing"
    assert s.lakehouse_bucket == "tbd-2026z-stud07-data-lakehouse"
    assert s.state_bucket == "tbd-2026z-stud07-mgmt-tfstate"
    assert s.region == "europe-west4"


def test_project_id_too_long_rejected():
    # tbd-2026z-studteam-alpha12-mgmt is 31 chars; GCP allows at most 30
    with pytest.raises(ConfigError, match="TF_VAR_team_id"):
        load_settings({**BASE, "TF_VAR_team_id": "team-alpha12"})


def test_thirty_char_project_id_accepted():
    s = load_settings({**BASE, "TF_VAR_team_id": "team-alpha1"})
    assert len(s.mgmt_project_id) == 30


def test_invalid_chars_rejected():
    with pytest.raises(ConfigError, match="TF_VAR_team_id"):
        load_settings({**BASE, "TF_VAR_team_id": "07_x"})


def test_missing_var_named():
    env = dict(BASE); del env["TF_VAR_billing_account"]
    with pytest.raises(ConfigError, match="TF_VAR_billing_account"):
        load_settings(env)


def test_blank_var_treated_as_missing():
    with pytest.raises(ConfigError, match="TF_VAR_notification_email"):
        load_settings({**BASE, "TF_VAR_notification_email": "  "})


def test_snowflake_account_split():
    s = load_settings(BASE)
    assert (s.sf_org, s.sf_account_name) == ("myorg", "tbd07")


def test_snowflake_locator_format_rejected():
    with pytest.raises(ConfigError, match="SNOWFLAKE_ACCOUNT"):
        load_settings({**BASE, "SNOWFLAKE_ACCOUNT": "xy12345.europe-west4.gcp"})


def test_supervisor_emails_parsed_from_json_list():
    s = load_settings({**BASE, "TF_VAR_supervisor_emails": '["x@y.pl", "z@w.pl"]'})
    assert s.supervisor_emails == ("x@y.pl", "z@w.pl")
    assert load_settings(BASE).supervisor_emails == ()


def test_supervisor_emails_must_be_json_list():
    with pytest.raises(ConfigError, match="TF_VAR_supervisor_emails"):
        load_settings({**BASE, "TF_VAR_supervisor_emails": "x@y.pl"})


def test_cli_prints_names_or_fails_with_exit_2(capsys):
    from tbd_lakehouse.config import main
    assert main(BASE) == 0
    assert "tbd-2026z-stud07-mgmt" in capsys.readouterr().out
    assert main({**BASE, "TF_VAR_team_id": "07_x"}) == 2
    assert "TF_VAR_team_id" in capsys.readouterr().err
