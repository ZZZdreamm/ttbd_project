-- The protected table: PII tagged from meta (see _silver.yml), row access on country.
select
    customer_id, first_name, last_name, email, phone, date_of_birth,
    street, city, postal_code, country, valid_from as updated_at
from {{ ref('customers_scd2') }}
where is_current
