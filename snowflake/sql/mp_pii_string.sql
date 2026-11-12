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
  -- MARKETING may segment customers but not identify them.
  WHEN CURRENT_ROLE() = 'MARKETING' THEN
    CASE SYSTEM$GET_TAG_ON_CURRENT_COLUMN('${tag}')
      -- every second character: Kowalski -> K*w*l*k*
      WHEN 'NAME'    THEN REGEXP_REPLACE(val, '(.).', '\\1*')
      -- pseudonym: same input, same output, so customers can be counted and joined
      WHEN 'EMAIL'   THEN LEFT(SHA2(LOWER(val)), 12)
      -- own idea: keep only the international dialling code (the country) when the number has one:
      -- +48 600 100 200 -> +48*********; a national number (no +) is fully masked: 886 547 213 -> *********
      WHEN 'PHONE'   THEN CASE WHEN LEFT(LTRIM(val), 1) = '+'
                               THEN LEFT(REGEXP_REPLACE(val, '[^0-9+]', ''), 3) || REPEAT('*', GREATEST(LENGTH(REGEXP_REPLACE(val, '[^0-9+]', '')) - 3, 0))
                               ELSE REPEAT('*', LENGTH(REGEXP_REPLACE(val, '[^0-9+]', ''))) END
      -- network only: 10.1.2.3 -> 10.1.0.0
      WHEN 'IP'      THEN SPLIT_PART(val, '.', 1) || '.' || SPLIT_PART(val, '.', 2) || '.0.0'
      WHEN 'CARD'    THEN '****'
      ELSE '***'
    END
  ELSE '***'
END
