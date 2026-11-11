"""`mise run sf:keygen`: one-time Snowflake bootstrap.

Generates the TERRAFORM_SVC key pair under .secrets/, prints the SQL the
student pastes into Snowsight (as the trial admin), and writes the Snowflake
CLI connection `tbd` to .secrets/config.toml (mise sets SNOWFLAKE_HOME there).
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tbd_lakehouse.config import ConfigError, Settings, load_settings

KEY_NAME = "terraform_svc.p8"
SECRETS = Path(__file__).resolve().parents[3] / ".secrets"


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def _public_der(key_path: Path) -> bytes:
    key = serialization.load_pem_private_key(key_path.read_bytes(), None)
    return key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def public_key_body(key_path: Path) -> str:
    """Base64 public key on one line, as Snowflake's RSA_PUBLIC_KEY expects."""
    return base64.b64encode(_public_der(key_path)).decode()


def public_key_fingerprint(key_path: Path) -> str:
    """The value Snowflake shows as RSA_PUBLIC_KEY_FP in DESC USER."""
    return "SHA256:" + base64.b64encode(hashlib.sha256(_public_der(key_path)).digest()).decode()


def generate_keypair(dir: Path) -> tuple[Path, str]:
    dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = dir / KEY_NAME
    if path.exists():
        raise FileExistsError(f"{path} already exists; delete it only if you also reset the user's key")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    _write_private(path, pem)
    return path, public_key_body(path)


def bootstrap_sql(public_key: str) -> str:
    """One statement per line, so each can be run (and checked) on its own."""
    return "\n".join(
        [
            "-- Run in a Snowsight SQL worksheet as the trial admin, ONE LINE AT A TIME",
            "-- (cursor on the line, Ctrl/Cmd+Enter). Each line says what it should print.",
            "-- 1) prints: Statement executed successfully.",
            "USE ROLE ACCOUNTADMIN;",
            "-- 2) prints: Warehouse WH_QUERY successfully created. (or already exists)",
            "CREATE WAREHOUSE IF NOT EXISTS WH_QUERY WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 "
            "AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;",
            "-- 3) prints: User TERRAFORM_SVC successfully created. (or already exists)",
            "CREATE USER IF NOT EXISTS TERRAFORM_SVC TYPE = SERVICE DEFAULT_ROLE = ACCOUNTADMIN "
            f"DEFAULT_WAREHOUSE = WH_QUERY RSA_PUBLIC_KEY = '{public_key}';",
            "-- 4) prints: Statement executed successfully. (makes reruns use this key)",
            f"ALTER USER TERRAFORM_SVC SET RSA_PUBLIC_KEY = '{public_key}';",
            "-- 5) prints: Statement executed successfully.",
            "GRANT ROLE ACCOUNTADMIN TO USER TERRAFORM_SVC;",
            "-- 6) RSA_PUBLIC_KEY_FP must equal the fingerprint printed by sf:keygen",
            "DESC USER TERRAFORM_SVC;",
            "-- 7) put this value into SNOWFLAKE_ACCOUNT in .env",
            "SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS snowflake_account;",
        ]
    )


def write_snow_connection(path: Path, settings: Settings, key_path: Path) -> None:
    text = "\n".join(
        [
            'default_connection_name = "tbd"',
            "",
            "[connections.tbd]",
            f'account = "{settings.snowflake_account}"',
            'user = "TERRAFORM_SVC"',
            'authenticator = "SNOWFLAKE_JWT"',
            f'private_key_file = "{key_path}"',
            'role = "ACCOUNTADMIN"',
            'warehouse = "WH_QUERY"',
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(text)
    path.chmod(0o600)


def main(env: Mapping[str, str] = os.environ, secrets: Path = SECRETS) -> int:
    try:
        settings = load_settings(env)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2
    key_path = secrets / KEY_NAME
    if key_path.exists():
        print(f"reusing existing key {key_path}")
        public_key = public_key_body(key_path)
    else:
        key_path, public_key = generate_keypair(secrets)
        print(f"generated {key_path}")
    write_snow_connection(secrets / "config.toml", settings, key_path)
    print(f"Snowflake CLI connection 'tbd' -> {secrets / 'config.toml'}")
    print(f"Expected RSA_PUBLIC_KEY_FP: {public_key_fingerprint(key_path)}\n")
    print(bootstrap_sql(public_key))
    print("\nThen check: mise exec -- snow sql -q 'select current_user()'  (should print TERRAFORM_SVC)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
