-- BRONZE: datos crudos tal como llegan (todo texto) + trazabilidad del archivo y del momento de carga.
CREATE TABLE IF NOT EXISTS bronze_transactions (
  id STRING, date STRING, type STRING, card STRING, amount STRING, currency STRING, merchant STRING,
  origen STRING, monto_conocido STRING, _source_file STRING, _ingested_at TIMESTAMP
) COMMENT 'Bronze: avisos del banco tal como llegan (sintético). Carga incremental con COPY INTO.'
-- COMMAND ----------
-- COPY INTO es idempotente: solo procesa archivos nuevos del Volume, sin duplicar lo ya cargado.
COPY INTO bronze_transactions FROM (
  SELECT id, date, type, card, amount, currency, merchant, origen, monto_conocido,
         _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
  FROM '/Volumes/${catalog}/gastos_demo/landing/transactions/'
) FILEFORMAT = CSV FORMAT_OPTIONS ('header' = 'true')
-- COMMAND ----------
-- dimensiones pequeñas: se recargan completas en cada corrida
CREATE OR REPLACE TABLE bronze_rules AS SELECT * FROM read_files('/Volumes/${catalog}/gastos_demo/landing/dims/rules.csv', format => 'csv', header => true)
-- COMMAND ----------
CREATE OR REPLACE TABLE bronze_category_tipo AS SELECT * FROM read_files('/Volumes/${catalog}/gastos_demo/landing/dims/category_tipo.csv', format => 'csv', header => true)
-- COMMAND ----------
CREATE OR REPLACE TABLE bronze_fx AS SELECT * FROM read_files('/Volumes/${catalog}/gastos_demo/landing/dims/fx.csv', format => 'csv', header => true)
-- COMMAND ----------
CREATE OR REPLACE TABLE bronze_ingresos AS SELECT * FROM read_files('/Volumes/${catalog}/gastos_demo/landing/dims/ingresos.csv', format => 'csv', header => true)
-- COMMAND ----------
CREATE OR REPLACE TABLE bronze_recurrentes AS SELECT * FROM read_files('/Volumes/${catalog}/gastos_demo/landing/dims/recurrentes.csv', format => 'csv', header => true)
-- COMMAND ----------
CREATE OR REPLACE TABLE bronze_statement_lines AS SELECT * FROM read_files('/Volumes/${catalog}/gastos_demo/landing/dims/statement_lines.csv', format => 'csv', header => true)
