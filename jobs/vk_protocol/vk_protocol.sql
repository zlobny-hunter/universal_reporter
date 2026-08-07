select * from llo.vk_protocol
where id = ANY(string_to_array(%(id)s, ',')::int[])