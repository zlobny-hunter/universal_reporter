SELECT p.NUMBER_, pr.*
FROM llo.PRESCRIPTION p
    JOIN llo.PRESCRIPTION_ROW pr ON pr.PRESCRIPTION_ID = p.ID
WHERE p.NUMBER_ = ANY(string_to_array(%(numbers)s, ','))
limit  10000