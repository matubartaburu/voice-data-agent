-- GOLD: tablas listas para consultar (y para que Genie las entienda sin lógica compleja).
CREATE OR REPLACE TABLE gold_monthly_category COMMENT 'Gasto por mes, moneda y categoría (sin ahorro). tipo = esencial o prescindible.' AS
SELECT month, currency, coalesce(category, 'Sin categoría') AS category, tipo,
       round(sum(amount_signed), 2) AS total, count(*) AS n_movements
FROM silver_transactions WHERE counts_as_spend
GROUP BY month, currency, coalesce(category, 'Sin categoría'), tipo
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_monthly_summary COMMENT 'Resumen mensual: total, fijos, variable (lo que gasta la persona sin fijos), prescindible y variación contra el mes anterior.' AS
WITH m AS (
  SELECT month, currency,
         round(sum(amount_signed), 2) AS total,
         round(sum(CASE WHEN origen = 'recurrente' THEN amount_signed END), 2) AS fixed_expenses,
         round(sum(CASE WHEN origen <> 'recurrente' THEN amount_signed END), 2) AS variable_spend,
         round(sum(CASE WHEN tipo = 'prescindible' AND origen <> 'recurrente' THEN amount_signed END), 2) AS discretionary_spend
  FROM silver_transactions WHERE counts_as_spend GROUP BY month, currency
)
SELECT *, round(discretionary_spend / nullif(variable_spend, 0) * 100, 1) AS discretionary_pct_of_variable,
       round(total - lag(total) OVER (PARTITION BY currency ORDER BY month), 2) AS total_change_vs_prev_month,
       round(discretionary_spend - lag(discretionary_spend) OVER (PARTITION BY currency ORDER BY month), 2) AS discretionary_change_vs_prev_month
FROM m
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_daily_spend COMMENT 'Gasto variable diario en pesos con promedio y suma móvil de 30 días (ventana). Incluye días sin gasto.' AS
WITH cal AS (SELECT explode(sequence((SELECT min(day) FROM silver_transactions), (SELECT max(day) FROM silver_transactions), interval 1 day)) AS day),
d AS (
  SELECT day, sum(amount_signed) AS spend,
         sum(CASE WHEN tipo = 'prescindible' THEN amount_signed ELSE 0 END) AS discretionary
  FROM silver_transactions WHERE counts_as_spend AND currency = 'UYU' AND origen <> 'recurrente' GROUP BY day
)
SELECT cal.day,
       round(coalesce(d.spend, 0), 2) AS variable_spend_uyu,
       round(avg(coalesce(d.spend, 0)) OVER (ORDER BY cal.day ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 2) AS rolling_30d_avg_uyu,
       round(sum(coalesce(d.discretionary, 0)) OVER (ORDER BY cal.day ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 2) AS discretionary_rolling_30d_total_uyu
FROM cal LEFT JOIN d ON d.day = cal.day
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_mtd_comparison COMMENT 'Mes en curso contra el mes anterior hasta el mismo día del mes, por moneda.' AS
WITH p AS (SELECT max(day) AS as_of FROM silver_transactions),
cur AS (
  SELECT s.currency, sum(s.amount_signed) AS spent, sum(CASE WHEN s.origen <> 'recurrente' THEN s.amount_signed END) AS variable
  FROM silver_transactions s, p WHERE s.counts_as_spend AND s.month = date_format(p.as_of, 'yyyy-MM') AND s.day <= p.as_of GROUP BY s.currency
), prev AS (
  SELECT s.currency, sum(s.amount_signed) AS spent, sum(CASE WHEN s.origen <> 'recurrente' THEN s.amount_signed END) AS variable
  FROM silver_transactions s, p WHERE s.counts_as_spend AND s.month = date_format(add_months(p.as_of, -1), 'yyyy-MM') AND s.day <= add_months(p.as_of, -1) GROUP BY s.currency
)
SELECT (SELECT as_of FROM p) AS as_of_date, cur.currency,
       round(cur.spent, 2) AS spent_to_date, round(prev.spent, 2) AS prev_month_same_point,
       round((cur.spent - prev.spent) / prev.spent * 100, 1) AS total_change_pct,
       round(cur.variable, 2) AS variable_to_date, round(prev.variable, 2) AS prev_variable_same_point,
       round((cur.variable - prev.variable) / prev.variable * 100, 1) AS variable_change_pct
FROM cur LEFT JOIN prev ON prev.currency = cur.currency
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_anomalies COMMENT 'Gastos atípicos: monto más de 3 desvíos estándar por encima del promedio de su categoría y moneda (z_score). Si la categoría tiene menos de 10 movimientos se compara contra todo el gasto variable de esa moneda.' AS
WITH s AS (
  SELECT *, avg(amount) OVER (PARTITION BY currency, category) AS mu_cat,
         stddev_samp(amount) OVER (PARTITION BY currency, category) AS sd_cat,
         count(*) OVER (PARTITION BY currency, category) AS n_cat,
         avg(amount) OVER (PARTITION BY currency) AS mu_cur,
         stddev_samp(amount) OVER (PARTITION BY currency) AS sd_cur
  FROM silver_transactions
  WHERE counts_as_spend AND origen <> 'recurrente' AND amount_known AND type IN ('debito', 'credito')
), z AS (
  SELECT *, CASE WHEN n_cat >= 10 THEN mu_cat ELSE mu_cur END AS mu,
         CASE WHEN n_cat >= 10 THEN sd_cat ELSE sd_cur END AS sd,
         CASE WHEN n_cat >= 10 THEN 'categoría' ELSE 'moneda' END AS compared_against
  FROM s
)
SELECT id, day, currency, coalesce(category, 'Sin categoría') AS category, merchant, amount,
       round(mu, 2) AS reference_avg, round((amount - mu) / sd, 2) AS z_score, compared_against
FROM z WHERE sd > 0 AND (amount - mu) / sd > 3
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_projection COMMENT 'Proyección de cierre del mes en curso: lo gastado, ritmo diario variable y fijos que todavía no se cobraron.' AS
WITH p AS (SELECT max(day) AS as_of FROM silver_transactions),
m AS (SELECT date_format(as_of, 'yyyy-MM') AS month, as_of, day(as_of) AS d, day(last_day(as_of)) AS days_total FROM p),
t AS (
  SELECT s.currency,
         sum(CASE WHEN s.origen <> 'recurrente' THEN s.amount_signed END) AS variable_to_date,
         sum(CASE WHEN s.origen = 'recurrente' THEN s.amount_signed END) AS fixed_to_date
  FROM silver_transactions s, m WHERE s.counts_as_spend AND s.month = m.month GROUP BY s.currency
), f AS (
  SELECT r.currency, sum(r.amount) AS fixed_pending FROM silver_recurrentes r, m WHERE r.day > m.d GROUP BY r.currency
)
SELECT m.month, m.as_of AS as_of_date, t.currency,
       round(t.variable_to_date, 2) AS variable_to_date, round(coalesce(t.fixed_to_date, 0), 2) AS fixed_to_date,
       round(coalesce(f.fixed_pending, 0), 2) AS fixed_pending,
       round(t.variable_to_date / m.d, 2) AS avg_daily_variable,
       round(t.variable_to_date / m.d * m.days_total + coalesce(t.fixed_to_date, 0) + coalesce(f.fixed_pending, 0), 2) AS projected_month_total
FROM t CROSS JOIN m LEFT JOIN f ON f.currency = t.currency
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_recurring COMMENT 'Pagos que se repiten todos los meses con monto casi fijo (suscripciones).' AS
SELECT merchant, currency, count(DISTINCT month) AS months_seen, round(avg(amount), 2) AS avg_amount,
       round(coalesce(stddev_samp(amount), 0), 2) AS amount_stddev, min(day) AS first_seen, max(day) AS last_seen
FROM silver_transactions
WHERE type IN ('debito', 'credito') AND counts_as_spend AND origen <> 'recurrente' AND amount_known
GROUP BY merchant, currency
HAVING count(DISTINCT month) >= 4 AND coalesce(stddev_samp(amount), 0) / avg(amount) < 0.05 AND count(*) <= count(DISTINCT month) * 1.2
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_income_vs_spend COMMENT 'Aportes recibidos en pesos contra gasto variable del mes y cuánto sobra.' AS
WITH i AS (SELECT date_format(day, 'yyyy-MM') AS month, sum(amount) AS income FROM silver_ingresos WHERE currency = 'UYU' GROUP BY 1),
s AS (SELECT month, sum(amount_signed) AS variable_spend FROM silver_transactions WHERE counts_as_spend AND currency = 'UYU' AND origen <> 'recurrente' GROUP BY month)
SELECT s.month, round(coalesce(i.income, 0), 2) AS income_uyu, round(s.variable_spend, 2) AS variable_spend_uyu,
       round(coalesce(i.income, 0) - s.variable_spend, 2) AS left_over_uyu,
       round(s.variable_spend / nullif(i.income, 0) * 100, 1) AS pct_of_income_used
FROM s LEFT JOIN i ON i.month = s.month
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_missing_in_mail COMMENT 'Líneas del estado de cuenta que no tienen un aviso por mail equivalente (mismo día, moneda y monto).' AS
SELECT l.line_id, l.day, l.concept, l.amount, l.currency, date_format(l.day, 'yyyy-MM') AS month
FROM silver_statement_lines l
LEFT ANTI JOIN silver_transactions t
  ON t.day = l.day AND t.currency = l.currency AND abs(abs(t.amount) - l.amount) < 0.01 AND t.origen <> 'recurrente'
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_reconciliation_monthly COMMENT 'Conciliación por mes: líneas del estado de cuenta, cuántas faltan en los mails y por cuánto dinero.' AS
SELECT date_format(l.day, 'yyyy-MM') AS month, l.currency, count(*) AS statement_lines,
       count(m.line_id) AS missing_in_mail, round(coalesce(sum(m.amount), 0), 2) AS amount_missing_in_mail,
       round(count(m.line_id) / count(*) * 100, 1) AS pct_missing
FROM silver_statement_lines l LEFT JOIN gold_missing_in_mail m ON m.line_id = l.line_id
GROUP BY date_format(l.day, 'yyyy-MM'), l.currency
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_weekday_pattern COMMENT 'Gasto variable en pesos por día de la semana y categoría.' AS
SELECT dayofweek(day) AS day_of_week_number, date_format(day, 'EEEE') AS weekday, coalesce(category, 'Sin categoría') AS category,
       count(*) AS n_movements, round(sum(amount_signed), 2) AS total, round(avg(amount_signed), 2) AS avg_ticket
FROM silver_transactions WHERE counts_as_spend AND currency = 'UYU' AND origen <> 'recurrente' AND amount_known
GROUP BY dayofweek(day), date_format(day, 'EEEE'), coalesce(category, 'Sin categoría')
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_usd_in_pesos COMMENT 'Gasto en dólares por mes convertido a pesos con la cotización de ese mes.' AS
SELECT t.month, round(sum(t.amount_signed), 2) AS usd_spend, f.usd_uyu AS exchange_rate, round(sum(t.amount_signed) * f.usd_uyu, 2) AS usd_spend_in_uyu
FROM silver_transactions t JOIN silver_fx f ON f.month = t.month
WHERE t.currency = 'USD' AND t.counts_as_spend GROUP BY t.month, f.usd_uyu
-- COMMAND ----------
CREATE OR REPLACE TABLE gold_ingestion_log COMMENT 'Qué archivos se cargaron, cuántas filas trajo cada uno y cuándo (frescura del dato).' AS
SELECT regexp_extract(_source_file, '([^/]+)$', 1) AS file_name, count(*) AS rows_loaded, max(_ingested_at) AS ingested_at,
       min(substr(date, 1, 10)) AS first_day, max(substr(date, 1, 10)) AS last_day
FROM bronze_transactions GROUP BY regexp_extract(_source_file, '([^/]+)$', 1)
