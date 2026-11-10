#!/usr/bin/env python3
"""Sube el dataset SINTÉTICO a un Volume de Databricks y corre el pipeline bronze -> silver -> gold.
  python3 demo/run_pipeline.py              # carga inicial + capas
  python3 demo/run_pipeline.py --advance    # sube el próximo día de incoming/ y reprocesa (incremental)"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from databricks_api import Client, DatabricksError  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SQL_FILES = ["01_bronze.sql", "02_silver.sql", "03_gold.sql", "04_log.sql"]


def run_sql_file(c, name):
    text = open(os.path.join(HERE, "sql", name), encoding="utf-8").read().replace("${catalog}", c.catalog)
    steps = [s.strip() for s in text.split("-- COMMAND ----------") if s.strip()]
    for i, step in enumerate(steps, 1):
        title = next((l[3:].strip() for l in step.splitlines() if l.startswith("-- ")), "")
        c.sql(step)
        print(f"  {name} [{i}/{len(steps)}] ok {title}")


def landing(c):
    return f"/Volumes/{c.catalog}/gastos_demo/landing"


def setup(c):
    c.sql(f"CREATE SCHEMA IF NOT EXISTS {c.catalog}.gastos_demo COMMENT 'Demo sintética: gastos personales inventados (medallion)'", use_schema=False)
    c.sql(f"CREATE VOLUME IF NOT EXISTS {c.catalog}.gastos_demo.landing COMMENT 'Archivos CSV de aterrizaje (datos sintéticos)'", use_schema=False)


def already_loaded(c, file_name):
    try:
        return int(c.sql(f"SELECT count(*) FROM bronze_transactions WHERE _source_file LIKE '%{file_name}'")[0][0]) > 0
    except DatabricksError:
        return False  # la tabla todavía no existe


def upload_initial(c):
    base = landing(c)
    # No se vuelve a subir lo ya cargado: reescribir un archivo cambia su fecha y COPY INTO podría releerlo.
    if not already_loaded(c, "transactions_initial.csv"):
        c.upload(os.path.join(DATA, "transactions", "transactions_initial.csv"), f"{base}/transactions/transactions_initial.csv")
    for f in sorted(glob.glob(os.path.join(DATA, "dims", "*.csv"))):
        c.upload(f, f"{base}/dims/{os.path.basename(f)}")
    print("  archivos sintéticos subidos (carga inicial + dimensiones)")


def advance(c):
    """Sube el siguiente archivo diario que todavía no está en Databricks."""
    base = landing(c)
    done = {r[0] for r in c.sql(f"SELECT DISTINCT regexp_extract(_source_file, '([^/]+)$', 1) FROM bronze_transactions")}
    for f in sorted(glob.glob(os.path.join(DATA, "incoming", "*.csv"))):
        if os.path.basename(f) not in done:
            c.upload(f, f"{base}/transactions/{os.path.basename(f)}")
            print(f"  nuevo día subido: {os.path.basename(f)}")
            return True
    print("  no quedan días nuevos en incoming/")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--advance", action="store_true")
    ap.add_argument("--reset", action="store_true", help="borra el esquema de la demo y vuelve a cargar desde cero")
    a = ap.parse_args()
    c = Client()
    _ = c.catalog  # detecta el catálogo (workspace en Free Edition)
    print(f"Catálogo: {c.catalog}")
    if a.reset:
        c.sql(f"DROP SCHEMA IF EXISTS {c.catalog}.gastos_demo CASCADE", use_schema=False)
        print("  esquema borrado: se recarga desde cero")
    if a.advance:
        if not advance(c):
            return 0
    else:
        setup(c)
        upload_initial(c)
    for name in SQL_FILES:
        run_sql_file(c, name)
    n = c.sql("SELECT count(*), max(day) FROM silver_transactions")[0]
    print(f"Listo. silver_transactions: {n[0]} filas, último día {n[1]}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DatabricksError as e:
        print("ERROR:", e)
        sys.exit(1)
