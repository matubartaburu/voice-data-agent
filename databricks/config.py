"""Minimal config loader: non-secret settings live in a git-ignored config.json at the repo root."""
import json
import os

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
