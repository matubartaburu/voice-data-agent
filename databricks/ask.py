#!/usr/bin/env python3
"""Pregunta a Genie desde la terminal:  python3 demo/ask.py "Were there any unusual expenses recently?" """
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genie_client import Genie  # noqa: E402

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]).strip()
    if not q:
        sys.exit('Uso: ask.py "tu pregunta"')
    o = Genie().ask(q)
    print(f"\n[{o['status']}] {o['latency_ms']} ms")
    if o["error"]:
        print("error:", o["error"])
    if o["text"]:
        print("\nRespuesta:", o["text"])
    if o["sql"]:
        print("\nSQL que generó Genie:\n" + o["sql"])
    if o["rows"]:
        print("\n" + " | ".join(map(str, o["columns"])))
        for r in o["rows"][:10]:
            print(" | ".join(map(str, r)))
