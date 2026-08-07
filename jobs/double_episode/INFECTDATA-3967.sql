with ss as (
    select e.epidemic_case_id as ep_c
    from episode e
    where type_id = 1204725444 and deleted is null
    group by e.epidemic_case_id
    having count(id)>1
  )
select distinct ss.ep_c
from ss
join episode e2 on e2.epidemic_case_id = ss.ep_c and e2.type_id = 1204725444 and e2.end_date is null and e2.deleted is null
join episode e3 on e3.epidemic_case_id = ss.ep_c and e3.type_id = 1204725444 and e3.end_date is not null and e3.deleted is null
join epidemic_case ec on ec.id = ss.ep_c and ec.end_date is null and ec.deleted is null