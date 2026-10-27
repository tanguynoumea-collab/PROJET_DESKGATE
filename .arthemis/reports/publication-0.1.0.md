# Publication 0.1.0

tag `v0.1.0` (objet 4df3266) / commit `3de963e` / 2026-10-26 (tag), 2026-10-27 (déploiement vérifié)

## Contenu

Section `[0.1.0] - 2026-10-26` de `CHANGELOG.md` : runner local, API pour n8n, exécution dans un Job Object,
rappel garanti avec `data` exposé et marqueurs de repli, capacités `ifc.clash` (BCF 2.1) et `mcp.call`,
installation (`init`, tâche planifiée, `doctor`, `purge`), compose n8n 2.43.8 et workflow d'exemple. Le cœur,
`deskgate-bim` et `deskgate-bcf` passent en 0.1.0.

## Prévisualisation

Sans palier : runner local mono-utilisateur, aucun environnement intermédiaire. La recette des vérifications humaines
(05-D2, 05.2-D1, 05.2-D2, 05.4-D2) a été jouée le 2026-10-26 sur l'installation réelle avant le tag.

## Migrations

Aucune. Schéma SQLite 2 inchangé (`SCHEMA_VERSION` 2), base existante conservée. Pas de sauvegarde requise.

## Déploiement

Cible : PC de l'utilisateur, `uv tool install --force .` sur le tag `v0.1.0` hors MSIX, tâche planifiée « Deskgate ».
Installé le 2026-10-26 ; redémarrage du PC le 2026-10-27 (démarrage 13:21:58, ouverture de session 13:34:21).

## Vérification 11a

| Contrôle | Résultat |
|---|---|
| L'application répond | ok : `/health` `{"status":"ok","version":"0.1.0","engine":"ok","sender":"ok"}` |
| Parcours critique | ok : n8n 2.43.8 exécution 15 `success`, tâche `57cf0aaad01b` (`ifc.clash`, `mur_gaine.ifc`), 1 conflit, BCF, rappel `delivered` en 1 essai, reprise par « Succes » |
| Les erreurs ne montent pas | réserve : aucune depuis le redémarrage ; 9 `database is locked` au repos entre 2026-10-26 21:43 et 2026-10-27 13:17, sans veille ni tâche, runner rétabli à chaque fois (finding `sqlite-verrou-repos`) |
| Migrations appliquées | sans objet, aucune migration |
| Retour arrière possible | ok : tag `v0.1.0` sur le dépôt distant, désinstallation documentée |

05-D1 constaté : le runner 0.1.0 a été lancé par la tâche planifiée à l'ouverture de session (`pythonw.exe` sous
`svchost`, 13:34:21). Résultat 11a : ok, avec la réserve ci-dessus. Le signal de déclenchement du retour arrière n'est
pas atteint.

Constat d'exploitation : après un redémarrage, Docker Desktop ne démarre pas seul ; les conteneurs n8n reprennent avec
Docker. Tant qu'il n'est pas lancé, n8n ne peut pas soumettre de tâche.

## Plan de retour arrière tel que validé

- Annulation du code : première version, aucune antérieure : `deskgate task end`, `deskgate task remove`, puis
  `uv tool uninstall deskgate`.
- Code d'avant compatible avec la base d'après : oui (réinstallation de la même version sur le schéma 2).
- Données écrites : base `%LOCALAPPDATA%\Deskgate` et dossiers `C:\BIM` conservés ; workflows n8n inchangés.
- Signal : vérification 11a en échec (runner non démarré par la tâche, `/health` KO ou parcours n8n sans reprise).
