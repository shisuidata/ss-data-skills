select
  r.dt,
  r.channel_id,
  count(distinct r.user_id) as register_user_cnt,
  count(distinct o.user_id) as pay_user_cnt,
  count(distinct o.user_id) / count(distinct r.user_id) as pay_rate
from dwd_user_register_d r
left join dwd_order_detail_d o
  on r.user_id = o.user_id
where r.dt between '2026-05-01' and '2026-05-14'
  and o.pay_status = 'success'
group by r.dt, r.channel_id;
