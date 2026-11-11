"""Snowflake connections for ops commands and tests.

Service users (TERRAFORM_SVC, INGEST_SVC) authenticate with a key pair in
.secrets/<user>.p8; demo users (ANALYST_USER, ...) with a PAT in
.secrets/<user>.pat (written by Terraform).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tbd_lakehouse.config import Settings, load_settings

SECRETS = Path(__file__).resolve().parents[2] / ".secrets"
SERVICE_USERS = {"TERRAFORM_SVC", "INGEST_SVC"}


def connect_kwargs(
    settings: Settings,
    role: str,
    user: str = "TERRAFORM_SVC",
    warehouse: str = "WH_QUERY",
    secrets: Path = SECRETS,
) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "account": settings.snowflake_account,
        "user": user,
        "role": role,
        "warehouse": warehouse,
    }
    if user.upper() in SERVICE_USERS:
        key = secrets / f"{user.lower()}.p8"
        if not key.exists():
            raise FileNotFoundError(f"missing {key} (run 'mise run sf:keygen' / 'mise run snowflake')")
        kw.update(authenticator="SNOWFLAKE_JWT", private_key_file=str(key))
    else:
        pat = secrets / f"{user.lower()}.pat"
        if not pat.exists():
            raise FileNotFoundError(f"missing {pat} (written by 'mise run snowflake')")
        kw.update(authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=pat.read_text().strip())
    return kw


def connect(role: str, user: str = "TERRAFORM_SVC", warehouse: str = "WH_QUERY", **extra: Any):
    import snowflake.connector

    kw = connect_kwargs(load_settings(), role, user, warehouse)
    kw.update(extra)
    return snowflake.connector.connect(**kw)
