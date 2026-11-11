select product_id, name, category, unit_price, updated_at
from {{ source('bronze', 'PRODUCTS_RAW') }}
where product_id is not null
qualify row_number() over (partition by product_id order by updated_at desc, _ingested_at desc) = 1
