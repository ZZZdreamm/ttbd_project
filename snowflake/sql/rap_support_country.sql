CURRENT_ROLE() IN (${all_rows_roles})
OR EXISTS (
  SELECT 1 FROM ${map_table} m
  WHERE m.user_name = CURRENT_USER() AND m.country = country
)
