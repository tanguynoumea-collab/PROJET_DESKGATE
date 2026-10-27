# Milestones

## v0.1 Runner minimal (Shipped: 2026-10-27)

**Version produit :** 0.1.0 (tag v0.1.0 sur 3de963e, .arthemis/reports/publication-0.1.0.md)

**Phases completed:** 9 phases (1, 2, 3, 4, 5, 5.1, 5.2, 5.3, 5.4), 72 plans ; 49/49 exigences ; backlog 999.1 à 999.10 non inclus
**Timeline:** 2026-10-20 → 2026-10-27

**Delivered:** n8n délègue une tâche longue au PC Windows et reprend fiablement quand elle se termine, quel que
soit le dénouement (succès, échec, délai, annulation, redémarrage du runner).

**Key accomplishments:**

- Runner local sur 127.0.0.1 : configuration typée, jeton haché, contrôle du Host, chemins `/data` ↔ `C:/BIM`
  validés contre les racines autorisées, instance unique (phase 1).
- File SQLite durable, exécution d'un plugin par tâche dans un Job Object Windows, délai avec arrêt de tout l'arbre,
  `interrupted` après arrêt brutal (phase 2).
- Rappel garanti vers la `resumeUrl` : outbox durable, politique n8n 2.43.8, plafond 1 Mio, signature masquée,
  audit local (phase 3) ; `data` exposé avec marqueurs de repli, rappels isolés, NaN refusés, purge (phase 5.4).
- Capacités `ifc.clash` (BCF 2.1 lisible dans BIMcollab Zoom, titres par gabarit, aucun conflit perdu) et
  `mcp.call` (serveur stdio déclaré, dans le Job Object) ; frontière GPL tenue par `deskgate-bcf` en sous-processus
  (phases 4 et 5.1).
- Installation sur la machine cible : `deskgate init`, tâche planifiée à l'ouverture de session, `doctor`, compose
  n8n 2.43.8 et workflow d'exemple ; calcul réel CVC × ARC de 486 s repris dans n8n (phase 5).
- Deux audits (saas-team-council, dev-senior) avec corrections et re-certifications : tous les findings fermés
  (phases 5.2, 5.3, 5.4).

**Known issues reportés :** finding `sqlite-verrou-repos` (verrous SQLite au repos, cycle suivant) ; backlog
999.1 à 999.10.

---
