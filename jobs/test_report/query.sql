SELECT 
    1 as id, 
    'Иван Иванов' as manager_name, 
    55000 as amount,
    '{current_date}' as report_generated_at
UNION ALL
SELECT 
    2 as id, 
    'Петр Петров' as manager_name, 
    73000 as amount,
    '{current_date}' as report_generated_at;