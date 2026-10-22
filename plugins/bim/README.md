# deskgate-bim : capacité `ifc.clash`

Détection de conflits (clash) entre éléments IFC avec `ifcclash` / IfcOpenShell (LGPL, utilisés comme
bibliothèques), regroupement par proximité et export BCF 2.1 optionnel. Le code de ce paquet est sous
licence MIT. Le sous-dossier `bcf/` (`deskgate-bcf`, GPL-3) n'est appelé **qu'en sous-processus**, avec
des fichiers JSON : `deskgate-bim` n'importe jamais `bcf-client`.

Installation des environnements et configuration de la capacité : voir [`AGENTS.md`](../../AGENTS.md)
§ 4 et le bloc d'exemples de `src/deskgate/runner.example.toml`.

## Paramètres

Tous les seuils sont en **mètres**, quelle que soit l'unité du fichier IFC. Un paramètre inconnu est
refusé (`invalid_params`).

| Nom | Type | Défaut | Rôle |
|---|---|---|---|
| `ifc_a` | chemin | obligatoire | Fichier IFC du côté A (chemin vu par n8n, converti par le runner) |
| `ifc_b` | chemin | absent | Fichier IFC du côté B ; sans lui, B vient de `ifc_a` |
| `selector_a` | texte | obligatoire | Sélecteur IfcOpenShell des éléments A |
| `selector_b` | texte | absent | Sélecteur du côté B ; sans lui (et sans `ifc_b`), A est comparé à lui-même |
| `mode` | `hard` ou `clearance` | obligatoire | Interférence ou distance minimale |
| `tolerance` | nombre (m, 0 à 1) | obligatoire en `hard` | Pénétration ignorée en dessous |
| `clearance` | nombre (m, > 0 à 10) | obligatoire en `clearance` | Distance minimale exigée |
| `group_radius` | nombre (m) | 2.0 | Rayon de regroupement des conflits voisins (0 : aucun regroupement) |
| `max_clashes` | entier | aucun (illimité) | Plafond optionnel de paires conservées ; s'il est atteint, `truncated` vaut vrai |
| `include_openings` | booléen | `false` | `false` : les réservations `IfcOpeningElement` sont exclues des deux sélections |
| `snapshots` | booléen | `true` | Génère une image PNG par point de vue du BCF |
| `title_template` | texte | `{type_a} x {type_b}` | Gabarit du titre des sujets (voir « Titre des sujets ») |
| `mappings` | objet | vide | Tables de correspondance `building`, `storey`, `trade`, `type` |
| `threads` | entier | settings, sinon min(4, CPU) | Threads de calcul de la géométrie |
| `bcf` | booléen | `false` | Produit `conflits.bcf` |
| `bcf_author` | texte | `deskgate` | Auteur des sujets BCF |
| `bcf_project` | texte | `ifc.clash` + noms de fichiers | Nom du projet BCF |
| `created_at` | ISO 8601 | maintenant (UTC) | Horodatage des sujets ; l'injecter rend le BCF reproductible |
| `context_radius` | nombre (m) | 5.0 | Rayon du contexte gris autour du conflit |
| `max_context` | entier | 500 | Éléments de contexte au plus par sujet (0 : aucun contexte) |

En `hard`, `distance` est la profondeur de pénétration. En `clearance`, un contact est une distance 0.

## Titre des sujets

Le titre de chaque sujet BCF vient d'un gabarit `title_template` et de tables `mappings` fournis par le job :
Deskgate ne contient aucun libellé ni code métier. Champs admis dans le gabarit (liste fermée) :

| Champ | Valeur brute |
|---|---|
| `building` | nom de l'`IfcBuilding` de l'élément principal A |
| `storey` | nom du niveau dont la cote encadre le point du conflit |
| `trade_a` / `trade_b` | nom de fichier de la maquette A / B, sans extension |
| `type_a` / `type_b` | nom du type d'objet IFC de l'élément principal, sinon sa classe |

Tables de `mappings` : `building`, `storey`, `trade` (sert `trade_a` et `trade_b`, clé = nom de fichier sans
extension) et `type` (sert `type_a` et `type_b`). Pour `type`, les clés sont essayées dans l'ordre
`<ClasseType>:<NomType>`, `<NomType>`, `<Classe>/<PREDEFINI>`, `<Classe>`, sur la classe du type, la classe de
l'élément puis ses surclasses.

Règles :

- champ inconnu ou accolade orpheline dans le gabarit : erreur `invalid_params` ;
- valeur absente d'une table fournie : valeur brute et avertissement `mapping_missing` ;
- champ introuvable : « ? » et avertissement `naming_incomplete` ;
- les tables ne changent que le texte : GUID et regroupement restent identiques ;
- un « / » dans une valeur est remplacé par « - » ; pas de suffixe « (+N) ».

Les paramètres complets du projet pilote PIC sont dans `n8n/examples/ifc-clash-params.json`. Extrait :

```json
{
  "title_template": "{building}/{storey}/{trade_a}-{trade_b}/{type_a} x {type_b}",
  "mappings": {
    "building": { "Jura": "BaJ", "Tour": "BaT" },
    "storey": { "J_10_P00": "P00", "J_11_P01": "P01" },
    "trade": { "PIC-EXE-AW-CVC-MNQ-BaJ-SUP-30701-IFC4": "CVC", "PIC_REV_HRS_ARC_MNQ_BaJ_SUP_30400": "ARC" },
    "type": { "IfcDuctSegment": "Gaine", "IfcCovering/CEILING": "Faux-plafond" }
  }
}
```

Ce qui donne par exemple `BaJ/P01/CVC-ARC/Gaine x Faux-plafond`.

## Sélecteurs

Syntaxe de sélecteur d'IfcOpenShell. Exemples :

- `IfcWall` : tous les murs ;
- `IfcWall, IfcSlab` : murs et dalles ;
- `IfcDuctSegment` : gaines.

Un sélecteur invalide donne `invalid_selector`. Un sélecteur qui ne retient aucun élément avec
géométrie n'est pas une erreur : un avertissement `selection_a_empty` ou `selection_b_empty` est ajouté.

## Sortie

- `summary` : `clashes`, `groups`, `truncated` (vrai seulement si le plafond `max_clashes` est atteint),
  `pairs_omitted`, `groups_omitted`, `warnings`, `warning_details`, `mode`, `unit`, seuil
  (`tolerance` ou `clearance`), `ifcopenshell`, `bcf` (booléen) et `bcf_topics` (entier).
- `data` : `counts`, `truncated`, puis `groups` (`id`, `centre`, `count`, `clashes` = paires). L'`id`
  d'un groupe est un UUID v5 déterministe. Si le résultat dépasse la taille du rappel, les paires sont
  omises (`pairs_omitted`, puis `groups_omitted` si les groupes eux-mêmes sont retirés) et l'artefact
  porte tout. `counts.openings_excluded` compte les réservations exclues.
- Artefacts : `clashes.json` (`kind: clashes`, toujours) et `conflits.bcf` (`kind: bcf`, si `bcf: true`
  et au moins un conflit). Sans conflit, l'avertissement `bcf_skipped_no_clash` est ajouté.

Avertissements possibles : `clashes_truncated`, `data_pairs_omitted`, `data_groups_omitted`,
`mapping_missing`, `naming_incomplete`, `naming_unavailable`, `snapshots_unavailable`,
`selection_a_empty`, `selection_b_empty`, `context_unavailable`, `bcf_skipped_no_clash`.

## Conventions BCF

Un sujet par groupe de conflits (son GUID est celui du groupe), de type `Clash`, statut `Open`, caméra
en perspective cadrée sur le centre du groupe. Chaque sujet a deux points de vue, sans sélection :

1. les deux objets du conflit seuls visibles : A en rouge (`FFE53935`), B en bleu (`FF1E88E5`) ;
2. seuls les objets du conflit et le contexte proche sont visibles (visibilité par défaut fausse,
   le reste de la maquette est masqué) : contexte gris transparent `40B0B0B0`, objets du conflit
   colorés comme dans la vue 1. Aucun élément visible n'est laissé sans couleur.

Les couleurs sont au format ARGB. Le contexte est calculé par un arbre géométrique et `select_box`
autour des éléments du conflit (`context_radius`) ; s'il échoue, l'avertissement `context_unavailable`
est ajouté et la vue 2 ne montre que le conflit.

Contrat d'écriture v2 : un PNG et un commentaire par point de vue ; le premier point de vue s'écrit
`viewpoint.bcfv` / `snapshot.png` (noms conventionnels lus par BIMcollab Zoom), les suivants
`<guid>.bcfv` / `<guid>.png`. Chaque `markup.bcf` porte un `Header` avec un `File` par maquette
distincte : `Filename` = nom du fichier IFC (jamais le chemin), `IfcProject` = GlobalId de son
`IfcProject`. Les caméras sont en coordonnées monde IFC. Les images sont rendues par logiciel (Pillow
et numpy) ; leur taille se règle par `settings.snapshot_size` de la capacité (défaut `[800, 450]`).

## Erreurs classées

| Code | Cause |
|---|---|
| `invalid_params` | Paramètres absents, inconnus ou hors bornes |
| `ifc_not_found` | Fichier IFC introuvable |
| `ifc_unreadable` | Fichier IFC illisible |
| `invalid_selector` | Sélecteur invalide |
| `memory` | Mémoire insuffisante pendant le calcul |
| `bcf_unavailable` | `settings.bcf_executable` absent, relatif ou inexistant |
| `bcf_contract_error` | Document refusé par `deskgate-bcf` (code 2) |
| `bcf_write_failed` | Échec ou délai dépassé de l'écriture du BCF |
| `memory_limit` | Attribué par le runner quand le plafond `memory_mb` du Job Object est atteint |

## Licence

MIT pour `src/deskgate_bim/`. `bcf/` est GPL-3 et n'est appelé que par chemin d'exécutable, en
sous-processus.
