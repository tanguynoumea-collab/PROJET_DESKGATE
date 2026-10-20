# Contrats JSON de Deskgate

## bcf-write-v1

`bcf-write-v1.json` est le JSON Schema (brouillon 2020-12) du fichier d'entrée de `deskgate-bcf write`.
`deskgate-bim` (MIT) écrit ce fichier ; `deskgate-bcf` (GPL-3) le valide puis produit le `.bcf`.
Aucun import croisé : le contrat est le seul lien entre les deux paquets.

### Champs

- `colors` : couleurs `AARRGGBB`. `a` = éléments A, `b` = éléments B, `context` = contexte gris
  transparent. Défauts : `FFE53935` (a), `FF1E88E5` (b), `40B0B0B0` (context).
- `camera` : `target` et `radius` en mètres, dans le repère monde IFC. `direction` facultatif.
- `context_guids` : facultatif ; liste de GUID IFC colorés avec `colors.context` dans la seconde vue.

### Règle de version

Toute modification incompatible crée un nouveau fichier `bcf-write-v2.json`. `deskgate-bcf` liste
les versions qu'il accepte.

### Règle des copies

Le fichier de `docs/contrats/` est la source de vérité. Deux copies identiques existent :
`plugins/bim/src/deskgate_bim/contracts/` et `plugins/bim/bcf/src/deskgate_bcf/schemas/`.
Modifier les trois ensemble ; un test compare les octets.

### Codes de sortie de `deskgate-bcf`

- `0` : succès ;
- `2` : entrée invalide ;
- `3` : écriture impossible.

Les messages sont en français, sur stderr.
