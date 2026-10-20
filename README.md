# Deskgate

**La porte d'entrée de n8n vers les outils lourds de votre PC Windows.**

n8n tourne dans Docker : il ne peut ni lancer un calcul IfcOpenShell de 40 minutes, ni piloter un
logiciel installé, ni démarrer un serveur MCP en stdio. Deskgate est un petit service local, dans
votre session Windows, à qui n8n délègue ces tâches : il les met en file, les exécute via des
plugins déclarés (Python, ligne de commande, MCP), puis rappelle n8n avec le résultat.

> Statut : en conception (v0.0). Rien n'est encore installable.

## Installation (cible)

```powershell
uv tool install deskgate
deskgate init
deskgate doctor
```

Procédure détaillée, aussi utilisable par une IA : [`AGENTS.md`](AGENTS.md).

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — conception technique
- [`ROADMAP.md`](ROADMAP.md) — versions et critères d'acceptation
- [`docs/passation/`](docs/passation/) — cadrage d'origine

## Licence

MIT — voir [`LICENSE`](LICENSE). Exception : le module BCF `plugins/bim/bcf/` (`deskgate-bcf`)
est sous GPL-3, car il s'appuie sur `bcf-client` ; il est appelé en programme séparé.
