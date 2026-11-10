-- SILVER: tipos correctos, hora local de Uruguay, monto con signo, categoría y tipo (esencial/prescindible).
CREATE TABLE IF NOT EXISTS silver_transactions (
  id STRING, ts TIMESTAMP, day DATE, month STRING, type STRING, card STRING, currency STRING,
  amount DOUBLE, amount_signed DOUBLE, merchant STRING, origen STRING, amount_known BOOLEAN,
  category STRING, tipo STRING, counts_as_spend BOOLEAN
) COMMENT 'Silver: movimientos limpios y categorizados. amount_signed resta los reembolsos; counts_as_spend excluye ahorro.'
-- COMMAND ----------
-- MERGE por id: reprocesar nunca duplica filas (idempotente).
MERGE INTO silver_transactions t USING (
  WITH base AS (
    SELECT id, to_timestamp(date) AS ts, type, card, trim(merchant) AS merchant, upper(trim(merchant)) AS merchant_norm,
           upper(trim(currency)) AS currency, CAST(amount AS DOUBLE) AS amount, origen,
           CAST(monto_conocido AS INT) = 1 AS amount_known
    FROM bronze_transactions
    QUALIFY row_number() OVER (PARTITION BY id ORDER BY _ingested_at DESC) = 1
  ), ruled AS (
    SELECT b.*, r.category,
           row_number() OVER (PARTITION BY b.id ORDER BY CAST(r.rule_id AS INT)) AS rn
    FROM base b LEFT JOIN bronze_rules r ON b.merchant_norm LIKE concat('%', upper(r.pattern), '%')
  )
  SELECT x.id, x.ts,
         CAST(from_utc_timestamp(x.ts, 'America/Montevideo') AS DATE) AS day,
         date_format(from_utc_timestamp(x.ts, 'America/Montevideo'), 'yyyy-MM') AS month,
         x.type, x.card, x.currency, x.amount,
         CASE WHEN x.type = 'reembolso' THEN -x.amount ELSE x.amount END AS amount_signed,
         x.merchant, x.origen, x.amount_known, x.category,
         coalesce(ct.tipo, 'sin_clasificar') AS tipo,
         coalesce(ct.excluded, 'false') <> 'true' AS counts_as_spend
  FROM ruled x LEFT JOIN bronze_category_tipo ct ON ct.category = x.category
  WHERE x.rn = 1
) s ON t.id = s.id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
-- COMMAND ----------
CREATE OR REPLACE TABLE silver_fx AS SELECT month, CAST(usd_uyu AS DOUBLE) AS usd_uyu FROM bronze_fx
-- COMMAND ----------
CREATE OR REPLACE TABLE silver_ingresos AS
SELECT id, CAST(date AS DATE) AS day, source, CAST(amount AS DOUBLE) AS amount, currency FROM bronze_ingresos
-- COMMAND ----------
CREATE OR REPLACE TABLE silver_recurrentes AS
SELECT name, CAST(amount AS DOUBLE) AS amount, currency, CAST(day AS INT) AS day, desde FROM bronze_recurrentes
-- COMMAND ----------
CREATE OR REPLACE TABLE silver_statement_lines AS
SELECT line_id, CAST(date AS DATE) AS day, concept, CAST(amount AS DOUBLE) AS amount, currency FROM bronze_statement_lines
