with orders as ({{ latest_orders() }}),
lines as ({{ order_lines('orders') }})
select
    to_date(l.placed_at) as order_date,
    coalesce(p.category, 'unknown') as category,
    count(distinct l.order_id) as orders,
    sum(l.qty) as units,
    sum(l.qty * l.unit_price)::number(12, 2) as revenue
from lines l
left join {{ ref('products') }} p on p.product_id = l.product_id
where l.status <> 'cancelled'
group by 1, 2
