SELECT
    p.number_,
    l.title,
    p.state AS state,
    p.e_recipe AS e_recipe,
    p.ctime::date AS ctime,
    erl.time_stamp::date AS time_stamp,
    erl.event_description,
    erl.pos_ident,
    ph.name_
FROM LLO.prescription p
JOIN LLO.E_Recipe_Log erl ON erl.prescription_id = p.id
JOIN LLO.lpu l ON p.lpu_id = l.id
JOIN LLO.Pharmacy ph ON ph.ident = erl.pos_ident
WHERE
    p.ctime >= (current_date-30)::timestamp AND p.ctime <= current_date::timestamp
    AND erl.time_stamp >= (current_date-30)::timestamp AND erl.time_stamp <= current_date::timestamp

    AND p.lpu_id <> 213511968
    AND p.number_ NOT IN ('00Д4516746364', '00Д4516883678')
    AND p.patient_id NOT IN (
        735544638, 201250921, 747788010, 747790701, 874332067, 874332316, 874330867, 874331332, 767881258, 222300388,
        228133558, 227368271, 809035981, 995043074, 197591609, 783686883, 241361390, 818326560, 823434818, 867209057,
        923641758, 925119680, 218266581, 217792418, 732189769, 215759225
    )

    AND p.type_ = 'commercial'
    AND (
       p.state = 23
       OR (p.state = 21 AND p.e_recipe IS NOT NULL AND erl.event_code = 'S' AND erl.event_result = '0')
   )
ORDER BY erl.time_stamp DESC;
