"""Team settings loaded from the environment (`.env`, loaded by mise).

All derived names (GCP project IDs, buckets, Snowflake account parts) come
from here so every tool agrees on them.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

REGION = "europe-west4"

# GCP project ID rules: 6-30 chars, lowercase letters/digits/hyphens,
# starts with a letter, doesn't end with a hyphen.
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_ID_PART = re.compile(r"^[a-z0-9-]+$")
# Snowflake org-account identifier, e.g. MYORG-MYACCOUNT (no locator/region form).
_SF_ACCOUNT = re.compile(r"^([A-Za-z0-9]+)-([A-Za-z0-9_]+)$")

REQUIRED = (
    "TF_VAR_semester",
    "TF_VAR_team_id",
    "TF_VAR_billing_account",
    "TF_VAR_notification_email",
    "SNOWFLAKE_ACCOUNT",
)


class ConfigError(ValueError):
    """A required setting is missing or invalid. The message names the variable."""


@dataclass(frozen=True)
class Settings:
    semester: str
    team_id: str
    billing_account: str
    notification_email: str
    snowflake_account: str
    supervisor_emails: tuple[str, ...] = ()
    region: str = REGION

    @property
    def _prefix(self) -> str:
        return f"tbd-{self.semester}-stud{self.team_id}"

    @property
    def mgmt_project_id(self) -> str:
        return f"{self._prefix}-mgmt"

    @property
    def data_project_id(self) -> str:
        return f"{self._prefix}-data"

    @property
    def landing_bucket(self) -> str:
        return f"{self.data_project_id}-landing"

    @property
    def lakehouse_bucket(self) -> str:
        return f"{self.data_project_id}-lakehouse"

    @property
    def state_bucket(self) -> str:
        return f"{self.mgmt_project_id}-tfstate"

    @property
    def sf_org(self) -> str:
        return self.snowflake_account.split("-", 1)[0]

    @property
    def sf_account_name(self) -> str:
        return self.snowflake_account.split("-", 1)[1]


def _require(env: Mapping[str, str], name: str) -> str:
    value = (env.get(name) or "").strip()
    if not value:
        raise ConfigError(f"{name} is not set (copy .env.example to .env and fill it in)")
    return value


def _supervisors(env: Mapping[str, str]) -> tuple[str, ...]:
    raw = (env.get("TF_VAR_supervisor_emails") or "").strip()
    if not raw:
        return ()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(
            'TF_VAR_supervisor_emails must be a JSON list of emails, e.g. ["a@uni.pl"]'
        )
    return tuple(value)


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    values = {name: _require(env, name) for name in REQUIRED}
    semester = values["TF_VAR_semester"].lower()
    team_id = values["TF_VAR_team_id"].lower()

    for var, part in (("TF_VAR_semester", semester), ("TF_VAR_team_id", team_id)):
        if not _ID_PART.match(part):
            raise ConfigError(f"{var}={part!r} may only contain letters, digits and hyphens")

    longest = f"tbd-{semester}-stud{team_id}-mgmt"  # -mgmt and -data are the same length
    if not _PROJECT_ID.match(longest):
        raise ConfigError(
            f"TF_VAR_team_id / TF_VAR_semester give project ID {longest!r} "
            f"({len(longest)} chars); GCP needs 6-30 lowercase letters, digits or hyphens"
        )

    account = values["SNOWFLAKE_ACCOUNT"]
    if not _SF_ACCOUNT.match(account):
        raise ConfigError(
            f"SNOWFLAKE_ACCOUNT={account!r} must be <org>-<account> "
            "(Snowsight: account menu > View account details > Account identifier)"
        )

    return Settings(
        semester=semester,
        team_id=team_id,
        billing_account=values["TF_VAR_billing_account"],
        notification_email=values["TF_VAR_notification_email"],
        snowflake_account=account,
        supervisor_emails=_supervisors(env),
    )


def main(env: Mapping[str, str] = os.environ) -> int:
    """`python -m tbd_lakehouse.config`: validate .env before any cloud call."""
    import sys

    try:
        s = load_settings(env)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2
    print(f"management project: {s.mgmt_project_id}")
    print(f"data project:       {s.data_project_id}")
    print(f"state bucket:       {s.state_bucket}")
    print(f"snowflake account:  {s.snowflake_account}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
