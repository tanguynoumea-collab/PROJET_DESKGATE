# Exécutée par <python de l'env> -I licenses_probe.py
import json
from importlib import metadata


def row(d):
    m = d.metadata
    return {
        "name": m["Name"],
        "version": d.version,
        "expr": m.get("License-Expression") or "",
        "license": (m.get("License") or "")[:200].replace("\n", " "),
        "classifiers": [
            c.split("::")[-1].strip()
            for c in m.get_all("Classifier", [])
            if c.startswith("License ::")
        ],
    }


print(
    json.dumps(sorted((row(d) for d in metadata.distributions()), key=lambda r: r["name"].lower()))
)
