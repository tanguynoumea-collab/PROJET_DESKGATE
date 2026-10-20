---
status: partial
phase: 04-capacit-s-v0-1
source: [04-07-PLAN.md]
started: 2026-10-20T00:00:00Z
updated: 2026-10-20T00:00:00Z
queue: deferred
horizon: none
overrides_bloquant: []
---

## Current Test

number: 1
name: Rendu du BCF ifc.clash dans BIMcollab Zoom (deux vues, contexte gris transparent, couleurs)
expected: Vue 1 : seuls les deux objets du conflit visibles, rouge et bleu ; vue 2 : maquette visible, contexte gris transparent, objets du conflit colorés ; caméra cadrée sur le conflit
awaiting: user response

## Tests

### 1. Rendu du BCF ifc.clash dans BIMcollab Zoom (deux vues, contexte gris transparent, couleurs)
expected: Vue 1 : seuls les deux objets du conflit visibles, rouge et bleu ; vue 2 : maquette visible, contexte gris transparent, objets du conflit colorés ; caméra cadrée sur le conflit
result: pending
id: 04-D1
kind: verify
source: 04-07/T2
where: Fichier conflits.bcf produit par ifc.clash sur une maquette réelle (dossier C:\BIM\travail\<job_id>\), ouvert dans BIMcollab Zoom avec l'IFC source
do: Ouvrir l'IFC puis le BCF, parcourir trois sujets, afficher pour chacun le point de vue 1 puis le point de vue 2
blocks: 5
if_fail: gap, /gsd:plan-phase 4 --gaps

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->
