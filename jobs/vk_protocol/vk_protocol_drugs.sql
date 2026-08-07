select vpd.* from llo.vk_protocol vp
         join llo.vk_protocol_drugs vpd on vp.id = vpd.protocol_id
where vp.id = ANY(string_to_array(%(id)s, ',')::int[])
