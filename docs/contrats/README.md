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

## bcf-write-v2

`bcf-write-v2.json` remplace v1 pour la phase 5.1 ; v1 reste inchangé. `deskgate-bcf` accepte les versions 1 et 2.

- `header_files` (facultatif, 1 à 16 entrées) : maquettes de référence, `filename` et `ifc_project`
  (GlobalId de l'`IfcProject`). Écrits en `Header/File` de chaque `markup.bcf` (`Filename`, attribut `IfcProject`).
- `camera` : `type`, `position`, `direction`, `up` obligatoires, en mètres dans le repère monde IFC
  (aucun décalage d'origine) ; `field_of_view` en degrés (défaut 60) ; `view_to_world_scale` pour l'orthogonale.
- `snapshots` (facultatif par sujet) : `only` et `context`, chemins PNG relatifs au dossier du JSON (jamais `..`
  ni absolu), PNG de 2 Mio au plus, vérifiés par `deskgate-bcf`.
- `topics` : jusqu'à 100000 sujets (plus de plafond pratique sur le volume de conflits).

Règles d'écriture v2 : le premier point de vue s'écrit `viewpoint.bcfv` + `snapshot.png`, le second
`<guid>.bcfv` + `<guid>.png`, avec `Index` 0 et 1 ; un `Comment` par point de vue.
