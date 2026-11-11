with orders as ({{ latest_orders() }}),
lines as ({{ order_lines('orders') }}),
delivered as (
    select coalesce(p.category, 'unknown') as category, sum(l.qty) as delivered_units
    from lines l left join {{ ref('products') }} p on p.product_id = l.product_id
    where l.status = 'delivered'
    group by 1
),
returned as (
    select coalesce(p.category, 'unknown') as category, sum(r.qty) as returned_units
    from {{ ref('returns') }} r left join {{ ref('products') }} p on p.product_id = r.product_id
    group by 1
)
select
    d.category,
    d.delivered_units,
    coalesce(r.returned_units, 0) as returned_units,
    round(coalesce(r.returned_units, 0) / nullif(d.delivered_units, 0), 4) as return_rate
from delivered d
left join returned r on r.category = d.category
