CASE
  WHEN CURRENT_ROLE() IN (${raw_roles}) THEN val
  WHEN CURRENT_ROLE() = 'SUPPORT' THEN DATE_FROM_PARTS(YEAR(val), 1, 1)
  -- own idea: decade of birth (a generation cohort for segmentation): 1987-06-14 -> 1980-01-01
  WHEN CURRENT_ROLE() = 'MARKETING' THEN DATE_FROM_PARTS(FLOOR(YEAR(val) / 10) * 10, 1, 1)
  ELSE NULL
END
