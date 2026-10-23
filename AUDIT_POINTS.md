# Points d'audit externe — Deskgate

Les 5 points sur lesquels l'audit externe (dev-senior, lecture seule) juge le projet **avant chaque publication**.
Validés par l'utilisateur le 2026-10-23. Toute modification est une décision explicite.

1. **Reprise fiable** — tout chemin de fin de tâche (succès, échec, délai dépassé, annulation, plantage du worker ou du
   runner, base verrouillée, thread de fond mort) aboutit à exactement un état terminal et à un rappel vers n8n au moins
   une fois ; aucun rappel n'est perdu en silence ; la reprise est bornée (superviseur, réessais, abandon en code 6).
2. **Frontières de sécurité** — aucune commande libre (pas de `shell=True`, pas de concaténation) ; plugins en
   sous-processus dans un Job Object ; tout chemin reçu converti puis validé contre `allowed_roots`, appels MCP compris ;
   écoute sur `127.0.0.1` et jeton sur toutes les routes sauf `/health` ; la signature de la `resumeUrl` n'est jamais
   écrite dans un journal, l'audit ni une réponse.
3. **Cœur générique et licences** — `src/deskgate` n'importe ni le BIM ni IfcOpenShell et ne connaît aucune clé de
   plugin ; seul `plugins/bim/bcf` (`deskgate-bcf`, GPL-3) importe `bcf-client` et il est appelé en sous-processus ;
   aucun code GPL ou AGPL ailleurs.
4. **Reprenabilité** — le runner (engine, sender, superviseur, store) et un plugin se comprennent en 10 minutes par un
   nouveau développeur ; `ARCHITECTURE.md` et `AGENTS.md` décrivent le code livré, pas une cible future.
5. **Prêt à distribuer** — installation reproductible (versions figées par le lock), tâche planifiée et `deskgate doctor`
   fiables (contexte MSIX compris), versions cohérentes des trois paquets, n8n épinglé (pas `latest`), documentation
   d'installation exacte (`README.md`, `AGENTS.md`).
