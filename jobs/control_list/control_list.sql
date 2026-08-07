with base as (select dl.id    as                                                     drugs_lists_id,
                     dl.title as                                                     drugs_lists_title,
                     dle.id   as                                                     drugs_list_entries_id,
                     case
                         when dle.trade_fname_id is not null then 'ПТН'
                         else case when dle.trade_name_id is not null then 'ОТН'
                                   when dle.trade_name_id is null then 'МНН' end
                                                                                 end drug_level,
                     dle.mnn_id,
                     dle.trade_name_id,
                     dle.trade_fname_id
              from llo.drugs_list_entries dle
                       join llo.drugs_lists dl on dle.list_id = dl.id
              where dle.mnn_id = ANY(string_to_array(%(mnn_id)s, ','))
                and dle.is_actual = 1
                and dl.is_actual = 1)
select
    drugs_lists_id,
    drugs_lists_title,
    drugs_list_entries_id,
    drug_level,
    case when drug_level = 'МНН' then b.mnn_id
        when drug_level = 'ОТН' then b.trade_name_id
        when drug_level = 'ПТН' then b.trade_fname_id end as drug_id,
    case when drug_level = 'МНН' then dem.rus_title
        when drug_level = 'ОТН' then dsn.rus_title
        when drug_level = 'ПТН' then dfn.rus_title end as drug_title,
    b.mnn_id,
    dem.rus_title as mnn_title
from base b
left join llo.drugs_ext_mnn dem on dem.id= b.mnn_id and dem.is_actual=1
left join llo.drugs_short_name dsn on dsn.id= b.trade_name_id and dsn.is_actual=1
left join llo.drugs_full_name dfn on dfn.id= b.trade_fname_id and dfn.is_actual=1
