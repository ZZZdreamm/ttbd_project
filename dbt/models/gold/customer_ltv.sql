-- Pseudonymised: customer_key = sha2(customer_id || salt); no PII columns.
with orders as ({{ latest_orders() }})
select
    sha2(customer_id || '{{ var("hash_salt") }}', 256) as customer_key,
    any_value(shipping_country) as country,
    count(*) as order_count,
    sum(total_amount)::number(12, 2) as ltv,
    min(placed_at) as first_order_at,
    max(placed_at) as last_order_at
from orders
where status = 'delivered'
group by customer_id
