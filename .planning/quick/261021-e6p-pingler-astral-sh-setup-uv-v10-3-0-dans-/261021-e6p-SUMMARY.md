# Tâche rapide 261021-e6p : épingler setup-uv sur v10.3.0

**Résumé :** la CI référence désormais `astral-sh/setup-uv@v10.3.0` (le tag majeur `v10` n'existe pas), ce qui débloque l'étape « Set up job ».

## Réalisation

- Fichier modifié : `.github/workflows/ci.yml` (ligne 11, 1 insertion / 1 suppression).
- `actions/checkout@v7` et le reste du workflow sont inchangés.
- Commit : `cbe3e56` `fix(quick-261021-e6p): épingler setup-uv sur v10.3.0 dans la CI`.
- Rien n'a été poussé.

## Écarts par rapport au plan

Aucun.

## Auto-vérification

- Commit cbe3e56 présent, un seul fichier touché.

## Self-Check: PASSED
