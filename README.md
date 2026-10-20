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

## Capacités v0.1

- `ifc.clash` : conflits IFC groupés en JSON et BCF 2.1 sur demande, voir
  [`plugins/bim/README.md`](plugins/bim/README.md) ;
- `mcp.call` : appel d'un outil d'un serveur MCP déclaré dans `runner.toml`.

Contrats JSON versionnés : [`docs/contrats/`](docs/contrats/). Installation des plugins et exemples de
configuration : [`AGENTS.md`](AGENTS.md) § 4.

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — conception technique
- [`ROADMAP.md`](ROADMAP.md) — versions et critères d'acceptation
- [`docs/passation/`](docs/passation/) — cadrage d'origine

## Licence

MIT — voir [`LICENSE`](LICENSE). Exception : le module BCF `plugins/bim/bcf/` (`deskgate-bcf`)
est sous GPL-3, car il s'appuie sur `bcf-client` ; il est appelé en programme séparé.
