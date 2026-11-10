"""Cliente de la Conversation API de Genie: pregunta, espera, lee el SQL y los datos, y REGISTRA cada interacción en Delta."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as core  # noqa: E402
from databricks_api import Client, DatabricksError  # noqa: E402

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}


def esc(s):
    return "NULL" if s is None else "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


class Genie:
    def __init__(self, space_id=None, client=None):
        self.c = client or Client()
        self.space = space_id or core.load_config().get("genie_space_id")
        if not self.space:
            raise DatabricksError("Falta genie_space_id en config.json (corré demo/genie_space.py).")
        self.base = f"/api/2.0/genie/spaces/{self.space}"

    def ask(self, question, conversation_id=None, timeout=240, log=True):
        t0 = time.time()
        out = {"question": question, "status": None, "text": None, "sql": None, "columns": [], "rows": [],
               "conversation_id": conversation_id, "latency_ms": None, "error": None}
        try:
            if conversation_id:
                r = self.c.request("POST", f"{self.base}/conversations/{conversation_id}/messages", {"content": question})
            else:
                r = self.c.request("POST", f"{self.base}/start-conversation", {"content": question})
            cid, mid = r.get("conversation_id"), r.get("message_id")
            out["conversation_id"] = cid
            msg = {}
            while time.time() - t0 < timeout:
                msg = self.c.request("GET", f"{self.base}/conversations/{cid}/messages/{mid}")
                out["status"] = msg.get("status")
                if out["status"] in TERMINAL:
                    break
                time.sleep(2)
            for att in msg.get("attachments", []) or []:
                if att.get("text") and not out["text"]:
                    out["text"] = att["text"].get("content")
                if att.get("query"):
                    out["sql"] = att["query"].get("query")
                    out["text"] = out["text"] or att["query"].get("description")
                    res = self.c.request("GET", f"{self.base}/conversations/{cid}/messages/{mid}/attachments/{att['attachment_id']}/query-result")
                    sr = res.get("statement_response", res)
                    cols = [col.get("name") for col in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
                    out["columns"], out["rows"] = cols, sr.get("result", {}).get("data_array", []) or []
            if out["status"] == "FAILED":
                out["error"] = str(msg.get("error"))[:300]
        except DatabricksError as e:
            out["status"], out["error"] = "ERROR", str(e)[:300]
        out["latency_ms"] = int((time.time() - t0) * 1000)
        if log:
            self.log(out)
        return out

    def log(self, o):
        try:
            self.c.sql(
                "INSERT INTO genie_interactions VALUES (current_timestamp(), "
                f"{esc(o['question'])}, {esc(o['conversation_id'])}, {esc(o['status'])}, {esc(o['sql'])}, "
                f"{len(o['rows'])}, {o['latency_ms']}, {esc(o['error'])})")
        except DatabricksError as e:  # el log nunca debe romper la respuesta
            print("(aviso: no pude registrar la interacción)", str(e)[:120])
