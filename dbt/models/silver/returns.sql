select return_id, order_id, product_id, qty, reason, returned_at
from {{ source('bronze', 'RETURNS_RAW') }}
where return_id is not null
qualify row_number() over (partition by return_id order by _ingested_at desc) = 1
