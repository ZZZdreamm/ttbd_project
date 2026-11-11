from tbd_lakehouse.ops.teardown import dbt_built_tables

# Shape of SHOW ICEBERG TABLES rows as returned by a DictCursor.
ROWS = [
    {"database_name": "LAKEHOUSE", "schema_name": "BRONZE", "name": "ORDERS_EVENTS",
     "base_location": "bronze/orders_events.0p1WKmG2/"},
    {"database_name": "LAKEHOUSE", "schema_name": "SILVER", "name": "CUSTOMERS_CURRENT",
     "base_location": "_dbt/SILVER/customers_current.AbC/"},
    {"database_name": "LAKEHOUSE", "schema_name": "GOLD", "name": "CUSTOMER_LTV",
     "base_location": "_dbt/GOLD/customer_ltv.rclbqppF/"},
    {"database_name": "LAKEHOUSE", "schema_name": "SILVER", "name": "ORDERS_LATEST",
     "base_location": "silver/orders_latest/"},
]


def test_only_dbt_tables_are_selected():
    assert dbt_built_tables(ROWS) == [
        '"LAKEHOUSE"."SILVER"."CUSTOMERS_CURRENT"',
        '"LAKEHOUSE"."GOLD"."CUSTOMER_LTV"',
    ]


def test_no_rows_means_nothing_to_drop():
    assert dbt_built_tables([]) == []
