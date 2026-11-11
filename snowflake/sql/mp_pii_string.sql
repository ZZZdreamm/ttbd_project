CASE
  -- Only the primary role counts: secondary roles must never unmask data.
  WHEN CURRENT_ROLE() IN (${raw_roles}) THEN val
  WHEN CURRENT_ROLE() = 'SUPPORT' THEN
    CASE SYSTEM$GET_TAG_ON_CURRENT_COLUMN('${tag}')
      WHEN 'NAME'  THEN LEFT(val, 1) || '***'
      WHEN 'EMAIL' THEN '***@' || SPLIT_PART(val, '@', 2)
      WHEN 'PHONE' THEN '***' || RIGHT(REGEXP_REPLACE(val, '[^0-9]', ''), 4)
      WHEN 'IP'    THEN SPLIT_PART(val, '.', 1) || '.' || SPLIT_PART(val, '.', 2) || '.x.x'
      WHEN 'CARD'  THEN val
      ELSE '***'
    END
  ELSE '***'
END
