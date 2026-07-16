select vep.* from llo.vk_protocol vp
         join llo.vk_err_process vep on vp.id = vep.protocol_id
where vp.id = ANY(string_to_array(%(id)s, ',')::int[])
