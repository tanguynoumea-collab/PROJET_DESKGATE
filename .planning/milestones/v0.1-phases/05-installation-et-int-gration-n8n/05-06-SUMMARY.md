---
phase: 05-installation-et-int-gration-n8n
plan: 06
subsystem: installation
tags: [uv-tool, planificateur, msix, doctor, ifcopenshell]
requires: ["05-03", "05-04", "05-05"]
provides:
  - "Deskgate installé sur la machine (uv tool install), runner démarré par le Planificateur"
  - "Environnements de plugins bim et bcf, capacité ifc.clash déclarée (memory_mb = 24576)"
  - "Jeton n8n écrit dans secrets\\jeton-n8n.txt (jamais affiché), consommé par 05-07"
affects: [05-07]
tech-stack:
  added: []
  patterns: ["installation exécutée hors du bac à sable MSIX de Claude"]
key-files:
  created: []
  modified: []
decisions:
  - "Installation exécutée depuis le terminal de l'application (non virtualisé), pas depuis le bac à sable MSIX (option A, voir STATE.md)"
metrics:
  duration: n/a
  completed: 2026-10-21
requirements-completed: [INS-01, INS-02]
---

# Phase 5 Plan 06 : installation réelle sur la machine

Deskgate est installé par `uv tool install`, initialisé, configuré pour `ifc.clash` et lancé par le Planificateur de tâches Windows ; `deskgate doctor` sort en code 0 avec 7 lignes [ok].

## Réalisé

- **Tâche 1** : `uv tool install --force .` donne `deskgate 0.1.0.dev0`. `deskgate init --yes` a été exécuté avec sa sortie redirigée vers `%LOCALAPPDATA%\Deskgate\secrets\jeton-n8n.txt` (45 octets) ; le contrôle du hachage affiche `hash_ok=True`. `deskgate task status` : « Tâche conforme », commande `...\uv\tools\deskgate\Scripts\pythonw.exe -m deskgate serve`.
- **Tâche 2** : environnements de plugins synchronisés sous `%LOCALAPPDATA%\Deskgate\plugins\bim` (ifcopenshell 0.9.0.post1) et `\bcf` (`deskgate-bcf --help` répond). Un seul bloc `[capabilities."ifc.clash"]`, `memory_mb = 24576`. Les deux maquettes sont dans `C:\BIM\depot` à la taille de la source (531804942 et 51088640 octets).
- **Tâche 3** : `deskgate task run` : « Runner démarré par le Planificateur ». `/health` renvoie `{"status":"ok","version":"0.1.0.dev0","warnings":[]}`. `deskgate doctor` : code 0, 7 lignes [ok] (Environnement, Configuration, Dossiers, Jeton, Tâche, Port « runner joignable », Plugins).

## Provenance du processus (vérifiée)

Processus à l'écoute sur 127.0.0.1:8765, lecture avec psutil :

| PID | Processus | Ligne de commande |
|---|---|---|
| 65128 | pythonw.exe | `...\uv\tools\deskgate\Scripts\pythonw.exe -m deskgate serve` |
| 97268 | pythonw.exe (parent, lanceur du venv) | même commande |
| 3812 | svchost.exe (Planificateur) | |
| 1908 | services.exe | |
| 1804 | wininit.exe | |

Aucun ancêtre bash, cmd, powershell, pwsh, WindowsTerminal ou Code : le runner descend de svchost, donc du Planificateur et non du terminal qui a lancé `task run`. Le journal `runner.log` contient 1 occurrence de « démarré (pid ».

## Deviations from Plan

### Incident de l'environnement

**1. [Rule 3 - Blocage] Virtualisation MSIX de %LOCALAPPDATA% / %APPDATA%**
- **Constaté pendant** : tâche 1, première tentative depuis le bac à sable de Claude.
- **Problème** : Claude est une application MSIX ; les écritures sous `%LOCALAPPDATA%` et `%APPDATA%` étaient redirigées vers `C:\Users\Tanguy\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache`, et la tâche planifiée échouait avec 0x8007010B (répertoire de travail introuvable pour le Planificateur).
- **Correctif** : option A (décision dans STATE.md). Copies virtualisées supprimées (`...\LocalCache\Local\Deskgate` et `...\Roaming\uv\tools\deskgate`), ancienne tâche « Deskgate » supprimée, puis installation complète rejouée depuis le terminal de l'application (non virtualisé, vérifié par un fichier marqueur) avec le script `C:\BIM\install\install.ps1`. Sorties : transcription `C:\BIM\install\install.log`, `C:\BIM\install\doctor.txt` (UTF-16), `C:\BIM\install\hash.out`.
- **Fichiers du dépôt modifiés** : aucun.

**Total** : 1 incident d'environnement, aucun changement de code. Aucune porte d'authentification.

## Known Stubs

Aucun.

## Notes

- Le jeton n'a été ni lu ni affiché par l'exécuteur. Le contenu de `secrets\jeton-n8n.txt` n'apparaît nulle part dans ce document.
- Le n8n de l'utilisateur (port 5678) n'a pas été touché ; le runner en cours n'a pas été arrêté.

## Self-Check: PASSED
