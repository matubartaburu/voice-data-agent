-- Registro de cada pregunta hecha a Genie: quedan trazables en Delta (pregunta, SQL generado, latencia, estado).
CREATE TABLE IF NOT EXISTS genie_interactions (
  ts TIMESTAMP, question STRING, conversation_id STRING, status STRING, generated_sql STRING,
  row_count INT, latency_ms BIGINT, error STRING
) COMMENT 'Log de interacciones con Genie para medir calidad y latencia del agente.'
