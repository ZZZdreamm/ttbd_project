from datetime import date

import pytest

from tests.live.helpers import one, tag_refs

pytestmark = pytest.mark.check("5 Masking")

SEED = ("INSERT INTO LAKEHOUSE.BRONZE.CUSTOMERS_RAW (CUSTOMER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE, DATE_OF_BIRTH, "
        "STREET, CITY, POSTAL_CODE, COUNTRY, UPDATED_AT, _FILE, _INGESTED_AT) SELECT 'TEST-1', 'Jan', 'Kowalski', "
        "'jan.kowalski@example.pl', '+48 600 100 200', '1990-05-17'::DATE, 'ul. Prosta 1', 'Warszawa', '00-001', 'PL', "
        "CURRENT_TIMESTAMP()::TIMESTAMP_NTZ, 'test', CURRENT_TIMESTAMP()")


@pytest.fixture(scope="module")
def seeded_customer(sf):
    c = sf("PIPELINE_ADMIN")
    c.cursor().execute("DELETE FROM LAKEHOUSE.BRONZE.CUSTOMERS_RAW WHERE CUSTOMER_ID = 'TEST-1'")
    c.cursor().execute(SEED)
    yield "TEST-1"
    c.cursor().execute("DELETE FROM LAKEHOUSE.BRONZE.CUSTOMERS_RAW WHERE CUSTOMER_ID = 'TEST-1'")


Q = ("SELECT first_name, email, phone, date_of_birth, street, city FROM LAKEHOUSE.BRONZE.CUSTOMERS_RAW "
     "WHERE customer_id = 'TEST-1'")


@pytest.mark.parametrize("role,first,email,phone,dob,street", [
    ("PII_ADMIN",      "Jan",  "jan.kowalski@example.pl", "+48 600 100 200", date(1990, 5, 17), "ul. Prosta 1"),
    ("PIPELINE_ADMIN", "Jan",  "jan.kowalski@example.pl", "+48 600 100 200", date(1990, 5, 17), "ul. Prosta 1"),
    ("SUPPORT",        "J***", "***@example.pl",          "***0200",         date(1990, 1, 1),  "***"),
    ("ANALYST",        "***",  "***",                     "***",             None,              "***"),
])
def test_bronze_masking_by_role(sf, seeded_customer, role, first, email, phone, dob, street):
    # TERRAFORM_SVC holds every role as a secondary role: masking must follow CURRENT_ROLE() only.
    row = one(sf(role), Q)
    assert (row["FIRST_NAME"], row["EMAIL"], row["PHONE"], row["DATE_OF_BIRTH"], row["STREET"]) == (first, email, phone, dob, street)
    assert row["CITY"] == "Warszawa"  # not PII


def test_bronze_pii_columns_tagged(sf):
    tags = tag_refs(sf("ACCOUNTADMIN"), "LAKEHOUSE.BRONZE.CUSTOMERS_RAW")
    assert tags == {"FIRST_NAME": "NAME", "LAST_NAME": "NAME", "EMAIL": "EMAIL", "PHONE": "PHONE",
                    "DATE_OF_BIRTH": "DOB", "STREET": "ADDRESS", "POSTAL_CODE": "ADDRESS"}
    orders = tag_refs(sf("ACCOUNTADMIN"), "LAKEHOUSE.BRONZE.ORDERS_EVENTS")
    assert orders == {"CARD_LAST4": "CARD", "IP_ADDRESS": "IP", "SHIPPING_STREET": "ADDRESS",
                      "SHIPPING_POSTAL_CODE": "ADDRESS"}
