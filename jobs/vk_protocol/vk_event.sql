select ve.* from llo.vk_protocol vp
         join llo.vk_event ve on vp.id = ve.protocol_id
where vp.id = ANY(string_to_array(%(id)s, ',')::int[])
