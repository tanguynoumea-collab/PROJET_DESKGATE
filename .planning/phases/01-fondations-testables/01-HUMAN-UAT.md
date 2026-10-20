---
status: partial
phase: 01-fondations-testables
source: [01-03-PLAN.md]
started: 2026-10-20T00:00:00Z
updated: 2026-10-20T00:00:00Z
queue: deferred
horizon: none
overrides_bloquant: []
---

## Current Test

number: 1
name: Spike D-13(a) : host.docker.internal joint un service lié à 127.0.0.1
expected: Le conteneur reçoit la liste de répertoire (code 0) et http.server journalise une requête GET 200 depuis une IP source à consigner dans 01-SUMMARY
awaiting: user response

## Tests

### 1. Spike D-13(a) : host.docker.internal joint un service lié à 127.0.0.1
expected: Le conteneur reçoit la liste de répertoire (code 0) et http.server journalise une requête GET 200 depuis une IP source à consigner dans 01-SUMMARY
result: pending
id: 01-D1
kind: verify
source: 01-03/T1
where: Machine cible, Docker Desktop démarré, terminal PowerShell
do: Démarrer Docker Desktop ; lancer `py -3.14 -m http.server 8799 --bind 127.0.0.1` ; dans un autre terminal `docker run --rm alpine wget -qO- http://host.docker.internal:8799/` (repli image `curlimages/curl`) ; noter le code de sortie et l'IP source affichée par http.server
blocks: 5
if_fail: gap, /gsd:plan-phase 1 --gaps (repli D-02 : allow_non_loopback sur l'IP vEthernet, traité en phase 5)

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->
