-- One row per customer version, ordered by the source's updated_at (not by arrival time).
with src as (
    select
        customer_id, first_name, last_name, email, phone, date_of_birth,
        street, city, postal_code, country, updated_at
    from {{ source('bronze', 'CUSTOMERS_RAW') }}
    where customer_id is not null and updated_at is not null
    -- the same version can arrive twice (file re-sent): keep the latest ingest
    qualify row_number() over (partition by customer_id, updated_at order by _ingested_at desc) = 1
)
select
    customer_id, first_name, last_name, email, phone, date_of_birth,
    street, city, postal_code, country,
    updated_at as valid_from,
    lead(updated_at) over (partition by customer_id order by updated_at) as valid_to,
    valid_to is null as is_current
from src
