"""Mise en place de n8n pour la recette : propriétaire, identifiant, workflow, contrôle INS-05.

Étapes idempotentes. Le jeton passe par stdin du conteneur, il n'est jamais affiché.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _commun import (
    DATA,
    N8N,
    RUNNER,
    WORKFLOW_ID,
    N8nSession,
    compose,
    http,
    read_env,
    wait_health,
)


def _etape(texte: str) -> None:
    print(texte, flush=True)


def _stderr(proc_stderr: bytes, secret: str) -> str:
    return proc_stderr.decode("utf-8", "replace").replace(secret, "***")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, default=DATA / "secrets" / "jeton-n8n.txt")
    args = parser.parse_args()
    env = read_env()

    _etape("1. attente de n8n (/healthz)")
    if not wait_health(N8N + "/healthz", 180):
        _etape("n8n ne répond pas")
        return 1

    _etape("2. propriétaire n8n")
    session = N8nSession()
    code, _ = http(
        "POST",
        N8N + "/rest/owner/setup",
        {
            "email": env["N8N_OWNER_EMAIL"],
            "firstName": env["N8N_OWNER_FIRST_NAME"],
            "lastName": env["N8N_OWNER_LAST_NAME"],
            "password": env["N8N_OWNER_PASSWORD"],
        },
    )
    if code == 200:
        _etape("propriétaire créé")
    elif session.login(env["N8N_OWNER_EMAIL"], env["N8N_OWNER_PASSWORD"]):
        _etape("propriétaire déjà créé (connexion réussie)")
    else:
        _etape(f"propriétaire inutilisable (HTTP {code})")
        return 1

    _etape("3. identifiant DeskgateToken0001 (jeton par stdin)")
    token = args.token_file.read_text(encoding="utf-8").strip()
    payload = [
        {
            "id": "DeskgateToken0001",
            "name": "Deskgate",
            "type": "httpHeaderAuth",
            "data": {"name": "Authorization", "value": "Bearer " + token},
        }
    ]
    done = compose(
        "exec",
        "-T",
        "-u",
        "node",
        "n8n",
        "n8n",
        "import:credentials",
        "--input=/dev/stdin",
        input_bytes=json.dumps(payload).encode("utf-8"),
        check=False,
    )
    if done.returncode != 0:
        _etape(
            f"import de l'identifiant en échec (code {done.returncode}) : "
            f"{_stderr(done.stderr, token)}"
        )
        return 1
    _etape("identifiant importé")

    _etape("4. import du workflow")
    compose("cp", "n8n/examples/ifc-clash.json", "n8n:/tmp/ifc-clash.json")
    done = compose(
        "exec",
        "-T",
        "-u",
        "node",
        "n8n",
        "n8n",
        "import:workflow",
        "--input=/tmp/ifc-clash.json",
        check=False,
    )
    if done.returncode != 0:
        _etape(
            f"import du workflow en échec (code {done.returncode}) : {_stderr(done.stderr, token)}"
        )
        return 1
    _etape("workflow importé")

    _etape("5. publication du workflow")
    done = compose(
        "exec",
        "-T",
        "-u",
        "node",
        "n8n",
        "n8n",
        "publish:workflow",
        f"--id={WORKFLOW_ID}",
        check=False,
    )
    voie = "CLI publish:workflow"
    if done.returncode != 0:
        voie = "API /activate"
        if not session.login(env["N8N_OWNER_EMAIL"], env["N8N_OWNER_PASSWORD"]):
            _etape("connexion impossible pour le repli API")
            return 1
        key_id, key = session.create_api_key("recette-setup")
        try:
            code, _ = http(
                "POST",
                f"{N8N}/api/v1/workflows/{WORKFLOW_ID}/activate",
                {},
                headers={"X-N8N-API-KEY": key},
            )
            if code != 200:
                _etape(f"activation par l'API refusée (HTTP {code})")
                return 1
        finally:
            session.delete_api_key(key_id)
    compose("restart", "n8n")
    if not wait_health(N8N + "/healthz", 180):
        _etape("n8n ne redémarre pas")
        return 1
    _etape(f"workflow publié (voie : {voie}) puis n8n redémarré")

    _etape("6. INS-05 : santé du runner et partage depuis le conteneur")
    sante = compose(
        "exec", "-T", "n8n", "wget", "-qO-", "http://host.docker.internal:8765/health", check=False
    )
    if sante.returncode != 0:
        _etape(f"runner injoignable depuis le conteneur (code {sante.returncode})")
        return 1
    _etape(sante.stdout.decode("utf-8", "replace").strip())
    listing = compose("exec", "-T", "n8n", "ls", "/data", check=False)
    contenu = listing.stdout.decode("utf-8", "replace").split()
    _etape("/data : " + " ".join(contenu))
    if not {"depot", "travail", "livrables"} <= set(contenu):
        _etape("/data ne liste pas depot, travail, livrables")
        return 1
    _etape(f"runner de référence : {RUNNER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
