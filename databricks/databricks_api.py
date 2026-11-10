"""Cliente mínimo de la API REST de Databricks (stdlib). El token sale del Keychain; nunca se imprime."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import config as core  # noqa: E402


class DatabricksError(RuntimeError):
    pass


def _token():
    r = subprocess.run(["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s",
                        "gastos-itau-databricks", "-w"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise DatabricksError("No hay token en el Keychain (servicio gastos-itau-databricks).")
    return r.stdout.strip()


class Client:
    def __init__(self):
        self.host = core.load_config().get("databricks_host")
        if not self.host:
            raise DatabricksError("Falta databricks_host en config.json")
        self._tok = _token()
        self._warehouse = None
        self._catalog = None

    def request(self, method, path, body=None, raw=None, timeout=120):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        headers = {"Authorization": f"Bearer {self._tok}"}
        headers["Content-Type"] = "application/octet-stream" if raw is not None else "application/json"
        req = urllib.request.Request(f"https://{self.host}{path}", method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = r.read()
                return json.loads(payload) if payload else {}
        except urllib.error.HTTPError as e:
            raise DatabricksError(f"HTTP {e.code} en {method} {path}: {e.read().decode(errors='replace')[:300]}")

    # ---- SQL ----
    @property
    def warehouse(self):
        if not self._warehouse:
            whs = self.request("GET", "/api/2.0/sql/warehouses").get("warehouses", [])
            if not whs:
                raise DatabricksError("No hay SQL warehouses.")
            self._warehouse = whs[0]["id"]
        return self._warehouse

    @property
    def catalog(self):
        if not self._catalog:
            self._catalog = self.sql("SELECT current_catalog()", use_schema=False)[0][0]
        return self._catalog

    def sql(self, statement, use_schema=True, schema="gastos_demo"):
        body = {"warehouse_id": self.warehouse, "statement": statement, "wait_timeout": "50s",
                "on_wait_timeout": "CONTINUE", "disposition": "INLINE", "format": "JSON_ARRAY"}
        if use_schema:
            _ = self.catalog  # asegura el catálogo para que los nombres sin calificar resuelvan en gastos_demo
        if use_schema and self._catalog:
            body.update({"catalog": self._catalog, "schema": schema})
        res = self.request("POST", "/api/2.0/sql/statements", body)
        deadline = time.time() + 600
        while res.get("status", {}).get("state") in ("PENDING", "RUNNING"):
            if time.time() > deadline:
                raise DatabricksError("Timeout esperando una consulta.")
            time.sleep(3)
            res = self.request("GET", f"/api/2.0/sql/statements/{res['statement_id']}")
        st = res.get("status", {})
        if st.get("state") != "SUCCEEDED":
            raise DatabricksError(f"SQL falló ({st.get('state')}): {st.get('error', {}).get('message', '')[:400]}")
        return res.get("result", {}).get("data_array", []) or []

    # ---- archivos en Volumes ----
    def upload(self, local_path, volume_path):
        with open(local_path, "rb") as f:
            self.request("PUT", f"/api/2.0/fs/files{volume_path}?overwrite=true", raw=f.read())
