# n8n pour Deskgate

Ce dossier contient un n8n épinglé (2.43.8) avec Postgres, et un workflow d'exemple `ifc.clash`.
Le compose publie n8n sur `127.0.0.1:5679` seulement : il coexiste avec un n8n déjà installé sur
le port 5678, qu'il ne touche pas.

## Démarrer

```bash
cd n8n
cp .env.example .env
```

Remplacer ensuite chaque valeur `a-remplacer` de `.env` (fichier ignoré par git). Pour générer un
secret : `python -c "import secrets; print(secrets.token_hex(32))"`. La clé `N8N_ENCRYPTION_KEY` doit
rester stable. Le mot de passe du propriétaire compte 8 caractères au moins, une majuscule, un chiffre.

```bash
docker compose pull
docker compose up -d
```

Attendre que `http://127.0.0.1:5679/healthz` réponde (premier démarrage : téléchargement des images).

## Importer l'exemple (CLI, sans clé d'API)

1. Créer le propriétaire, par l'interface au premier accès ou par `POST /rest/owner/setup`
   (`email`, `firstName`, `lastName`, `password`).
2. Créer l'identifiant « Deskgate » d'id `DeskgateToken0001` (type `httpHeaderAuth`, nom
   `Authorization`, valeur `Bearer <jeton>`). Le jeton passe par l'entrée standard, jamais par un
   fichier :
   `docker compose exec -T -u node n8n n8n import:credentials --input=/dev/stdin`
3. Importer le workflow (son `id` fixe est obligatoire) :
   `docker compose cp examples/ifc-clash.json n8n:/tmp/ifc-clash.json` puis
   `docker compose exec -T -u node n8n n8n import:workflow --input=/tmp/ifc-clash.json`
4. Publier puis redémarrer, pour que le webhook de production soit enregistré :
   `docker compose exec -T -u node n8n n8n publish:workflow --id=DeskgateClash0001` puis
   `docker compose restart n8n`

`scripts/recette/n8n_setup.py` automatise ces étapes.

## Lancer

- Interface : ouvrir le workflow et utiliser le déclencheur « Lancement manuel ».
- Webhook : `POST http://127.0.0.1:5679/webhook/deskgate-ifc-clash` avec
  `{"params": {...}, "timeout": 14400}`. Un 404 juste après la publication signifie que le webhook
  n'est pas encore enregistré : réessayer après quelques secondes.

Le workflow soumet la tâche à `http://host.docker.internal:8765/jobs` avec
`callback.url = {{ $execution.resumeUrl }}`, puis attend le rappel (nœud Wait, 6 h au plus, au-delà
du délai de la tâche). Les maquettes se lisent sous `/data/depot/`. Aucun second exemple `mcp.call`
n'est fourni dans cette phase.

## Lire le résultat

- Branche « Succes » : `resume`, `artefacts`, et le rapport au chemin
  `/data/travail/<job_id>/conflits.bcf`.
- Corps du rappel : `$json.body.summary`, `$json.body.data` (sortie du plugin, par exemple `structured_content`
  pour `mcp.call`), `$json.body.artifacts`. Si `data` vaut `{"path": "…/data.json", "truncated": true}`, lire le
  fichier à ce chemin (`/data/travail/<job_id>/`) ; `{"purged": true}` signifie que `deskgate purge` l'a retiré de
  la base.
- Branche « Echec ou delai » : `failed`, `timeout`, `cancelled`, `interrupted`, ou échéance du Wait
  sans rappel (`delai_depasse_sans_rappel`).

Le test porte sur `$json.body?.status` et non sur `$json.status` : à l'échéance du Wait, n8n
continue avec l'item d'entrée (la réponse `queued` du runner, sans clé `body`). Tester `$json.status`
donnerait un faux diagnostic.

## Avec un n8n déjà installé (port 5678)

Ne rien changer à sa configuration. Importer à la main (Import from file) le fichier
`examples/ifc-clash.json`, créer l'identifiant « Header Auth » nommé « Deskgate » (nom
`Authorization`, valeur `Bearer <jeton>`), puis exécuter par le déclencheur manuel. Sa
`WEBHOOK_URL` (ou `N8N_WEBHOOK_URL`) doit désigner `127.0.0.1` ou `localhost` pour que le runner
accepte la resumeUrl.

## Arrêter / revenir en arrière

- `docker compose down` : arrête et supprime les conteneurs, les données sont conservées.
- `docker compose down -v` : efface aussi la base n8n et ses identifiants.
