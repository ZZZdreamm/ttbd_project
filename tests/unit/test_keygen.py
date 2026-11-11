import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization

from tbd_lakehouse.config import load_settings
from tbd_lakehouse.ops.keygen import (
    bootstrap_sql,
    generate_keypair,
    main,
    public_key_fingerprint,
    write_snow_connection,
)

ENV = {"TF_VAR_semester": "2026z", "TF_VAR_team_id": "07", "TF_VAR_billing_account": "x",
       "TF_VAR_notification_email": "a@b.pl", "SNOWFLAKE_ACCOUNT": "MYORG-TBD07"}


def test_keypair_written_private_and_public_is_single_line(tmp_path):
    key, pub = generate_keypair(tmp_path)
    assert key == tmp_path / "terraform_svc.p8"
    assert key.stat().st_mode & 0o777 == 0o600
    assert "BEGIN" not in pub and "\n" not in pub
    assert key.read_text().startswith("-----BEGIN PRIVATE KEY-----")  # PKCS8, unencrypted


def test_bootstrap_sql_creates_service_user_with_key():
    sql = bootstrap_sql("MIIB...")
    assert "CREATE USER IF NOT EXISTS TERRAFORM_SVC" in sql
    assert "TYPE = SERVICE" in sql
    assert "RSA_PUBLIC_KEY = 'MIIB...'" in sql
    assert "GRANT ROLE ACCOUNTADMIN TO USER TERRAFORM_SVC" in sql


def test_bootstrap_sql_resets_key_on_rerun_and_creates_warehouse():
    sql = bootstrap_sql("MIIB...")
    assert "ALTER USER TERRAFORM_SVC SET RSA_PUBLIC_KEY = 'MIIB...'" in sql
    assert "CREATE WAREHOUSE IF NOT EXISTS WH_QUERY" in sql and "AUTO_SUSPEND = 60" in sql
    assert sql.index("USE ROLE ACCOUNTADMIN") < sql.index("CREATE USER")


def test_bootstrap_sql_is_one_statement_per_line():
    stmts = [l for l in bootstrap_sql("K").splitlines() if l.strip() and not l.startswith("--")]
    assert all(l.rstrip().endswith(";") for l in stmts)


def test_keygen_refuses_to_overwrite_existing_key(tmp_path):
    generate_keypair(tmp_path)
    with pytest.raises(FileExistsError):
        generate_keypair(tmp_path)


def test_fingerprint_is_sha256_of_der_public_key(tmp_path):
    key, _ = generate_keypair(tmp_path)
    k = serialization.load_pem_private_key(key.read_bytes(), None)
    der = k.public_key().public_bytes(serialization.Encoding.DER,
                                      serialization.PublicFormat.SubjectPublicKeyInfo)
    expected = "SHA256:" + base64.b64encode(hashlib.sha256(der).digest()).decode()
    assert public_key_fingerprint(key) == expected


def test_snow_connection_file(tmp_path):
    key, _ = generate_keypair(tmp_path)
    cfg = tmp_path / "config.toml"
    write_snow_connection(cfg, load_settings(ENV), key)
    text = cfg.read_text()
    assert 'default_connection_name = "tbd"' in text and "[connections.tbd]" in text
    for line in ('account = "MYORG-TBD07"', 'user = "TERRAFORM_SVC"', 'authenticator = "SNOWFLAKE_JWT"',
                 'role = "ACCOUNTADMIN"', 'warehouse = "WH_QUERY"', f'private_key_file = "{key}"'):
        assert line in text
    assert cfg.stat().st_mode & 0o777 == 0o600


def test_main_reuses_existing_key(tmp_path, capsys):
    assert main(ENV, secrets=tmp_path) == 0
    first = (tmp_path / "terraform_svc.p8").read_bytes()
    assert main(ENV, secrets=tmp_path) == 0
    assert (tmp_path / "terraform_svc.p8").read_bytes() == first
    out = capsys.readouterr().out
    assert "reusing existing key" in out and "SHA256:" in out
