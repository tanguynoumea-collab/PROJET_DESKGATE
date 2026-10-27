---
phase: 03-rappel-fiable
plan: 06
subsystem: sender
tags: [callback, httpx2, outbox, retry]
requires: ["03-01", "03-02", "03-03", "03-04"]
provides:
  - "deskgate.sender.Sender : tick, run, start, stop, wake, on_fatal, failed, last_tick_at"
  - "deskgate.sender.make_client et SendOutcome ; seul module de src/ important httpx2"
  - "tests/_support/sender_helpers.py : FakeWall, make_terminal, aides de lecture de base"
affects: [03-07]
tech-stack:
  added: []
  patterns: [thread miroir de l'engine piloté par tick(), horloge murale injectée, resumeUrl envoyée en chaîne brute avec corps bytes]
key-files:
  created:
    - src/deskgate/sender.py
    - tests/_support/sender_helpers.py
    - tests/fs/test_sender_send.py
    - tests/fs/test_sender_retry.py
    - tests/fs/test_sender_policy.py
  modified: []
decisions:
  - "Les exigences CB-01, CB-02, CB-03, CB-05, SEC-05 et SEC-06 restent Pending : le sender n'est pas encore câblé dans deskgate serve (03-07), donc aucun rappel réel n'est émis de bout en bout"
metrics:
  tasks: 2
  completed: 2026-10-20
---

# Phase 3 Plan 06: Thread sender Summary

Thread `Sender` qui réclame un rappel échu, revérifie l'hôte, construit le corps depuis la ligne `jobs`, envoie la `resumeUrl` telle quelle avec `httpx2`, classe la réponse et enregistre le résultat en base (réessais durables, abandon par fenêtre ou hôte refusé).

## Tâches

1. Thread sender et envoi de la resumeUrl telle quelle : `c39359a`
2. Réessais durables et politique de réponse de bout en bout : `0c813d8`

## Vérification

`pytest -m "not e2e"` : 466 réussis, 1 sauté (privilège de lien symbolique). `ruff check`, `ruff format --check`, `pyright` verts ; `tests/architecture` vert (httpx2 importé seulement par `sender.py`).
Tests : 9 dans test_sender_send.py (5 statuts, amorçage 2 s, 413 puis renvoi minimal, hôte revérifié, thread start/stop), 6 dans test_sender_retry.py (délais 2/4/8 s avec gigue, plafond, fenêtre, reprise par un second Sender, écriture préalable observée par `MockTransport`, coupure réseau), 13 dans test_sender_policy.py (9 scénarios de réponse paramétrés, réessai court, 409 illisible, 500, absence de signature en audit, base et journaux `deskgate.sender`).

## Deviations from Plan

**1. [Process] Tests et implémentation de la tâche 1 committés ensemble** (pas de commit RED séparé).

**2. [Rule 3 - Blocage] Lint** : `random.Random()` signalé par ruff S311 (gigue, non cryptographique) : `noqa` ciblé dans `sender.py` et dans l'aide de test.

**3. [Ajout mineur]** Un test supplémentaire (thread réel démarré, réveillé, arrêté deux fois) pour atteindre les 9 tests exigés par le critère d'acceptation de la tâche 1.

Aucun écart dans `store.py`, `classify` ni la table de décision.

## Known Stubs

Aucun.

## Self-Check: PASSED
