{#
  Latest status per order from the (possibly duplicated, out-of-order) event stream.
  Only non-PII columns: gold must stay readable from DuckDB without masking.
#}
{% macro latest_orders() %}
    select
        order_id, customer_id, items_json, total_amount, shipping_country,
        event_type as status,
        min(event_ts) over (partition by order_id) as placed_at
    from (
        select * from {{ source('bronze', 'ORDERS_EVENTS') }}
        qualify row_number() over (partition by event_id order by event_ts) = 1
    )
    qualify row_number() over (
        partition by order_id
        order by event_ts desc,
                 case event_type when 'delivered' then 4 when 'cancelled' then 4 when 'shipped' then 3
                                 when 'paid' then 2 else 1 end desc
    ) = 1
{% endmacro %}

{% macro order_lines(orders) %}
    select o.order_id, o.status, o.placed_at,
           l.value:product_id::string as product_id,
           l.value:qty::number as qty,
           l.value:unit_price::number(10, 2) as unit_price
    from {{ orders }} o, lateral flatten(input => parse_json(o.items_json)) l
{% endmacro %}
