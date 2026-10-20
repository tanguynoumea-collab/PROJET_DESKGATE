---
name: gsd-file-manuelle
description: Règle de classement des interventions humaines dans les plans GSD d'un projet piloté par ARTHEMIS en mode auto. Bloquant (B1 valeur consommée, B2 irréversible, B3 mains humaines) ou différable. Lue par gsd-planner, gsd-plan-checker et gsd-executor.
---

# gsd-file-manuelle

Skill de projet. Copiée par ARTHEMIS depuis `arthemis-orchestrator/assets/gsd-file-manuelle-SKILL.md` vers `<projet>/.claude/skills/gsd-file-manuelle/SKILL.md` à l'ouverture d'un cycle. ARTHEMIS compare le hash à chaque session. GSD 1.30 n'est pas modifié.

## Qui lit cette skill et quand [tous profils]

GSD injecte lui-même les skills de projet dans ses agents. Lignes exactes, vérifiées dans GSD 1.30 :

- gsd-planner, `~/.claude/get-shit-done/workflows/plan-phase.md:498` : `**Project skills:** Check .claude/skills/ or .agents/skills/ directory (if either exists) — read SKILL.md files, plans should account for project skill rules`
- gsd-plan-checker, `~/.claude/get-shit-done/workflows/plan-phase.md:597` : `**Project skills:** Check .claude/skills/ or .agents/skills/ directory (if either exists) — verify plans account for project skill rules`
- gsd-executor, `~/.claude/get-shit-done/workflows/execute-phase.md:259` : `.claude/skills/ or .agents/skills/ (Project skills, if either exists — list skills, read SKILL.md for each, follow relevant rules during implementation)`

Le gsd-researcher la lit aussi (`plan-phase.md:311`), sans obligation.

Rôles :
- gsd-planner : classe chaque intervention humaine. C'est le seul moment de classement.
- gsd-plan-checker : contrôle la forme et la cohérence (cinq contrôles, plus bas).
- gsd-executor : exécute. Il ne classe jamais, ne convertit jamais, ne saute jamais.
- Le mod `argos` vérifie la forme à l'écriture du PLAN.md et écrit la file `NN-HUMAN-UAT.md`. Il n'est pas un agent GSD.

## Classification [tous profils]

Toute étape qu'un humain doit jouer est classée AU MOMENT DU PLAN par le gsd-planner, contrôlée par le gsd-plan-checker, vérifiée en forme par le mod (lint de la trace `<blocking kind>`). L'exécuteur ne classe jamais.

BLOQUANTE si au moins un critère est vrai :

- B1 VALEUR CONSOMMÉE : une tâche auto ultérieure (même plan, vague supérieure, ou phase ultérieure dont `**Depends on**` cite celle-ci) a besoin d'une valeur que seul l'humain produit : relevé, horodatage, capture, fichier, identifiant, choix entre options non équivalentes. Test : peut-on rédiger l'`<action>` de la tâche suivante avec des valeurs concrètes sans connaître la réponse ? Non = B1. Exemple réel : 27-01, LUE-02 réécrite d'après les heures relevées (exemple OVERLAY, desktop_net).
- B2 IRRÉVERSIBLE : l'étape auto qui suit publie, déploie, tague, migre, envoie, paie ou supprime, et la vérification humaine en est la condition. Test déterministe : verbes publish/deploy/tag/release/migrate/send/delete ou appel à `references/publication.md` dans les tâches aval. Exemple : constat de release AVANT publication. [desktop_net] : `gh release create`, `git push --tags`. [web_saas] : déploiement en production (Vercel, Netlify), migration de base, envoi d'e-mails réels.
- B3 MAINS HUMAINES : `checkpoint:human-action` (`references/checkpoints.md`, type `human-action`), porte d'authentification (401/403, « Please run … login »), code 2FA, lien e-mail, approbation OAuth. Planifiable quand le geste est connu au plan (secret à poser, compte à créer, login) ; les portes 401/403, 2FA et OAuth imprévues sont créées à l'exécution et toujours bloquantes. Jamais pour un travail manuel pré-planifié qui a un CLI ou une API (déployer, créer une base, lancer un build).

Sinon DIFFÉRABLE : sa seule sortie est un verdict pass/issue sur un comportement déjà construit ; un issue se traite par `/gsd:plan-phase N --gaps` puis `/gsd:execute-phase N --gaps-only`. Différables par défaut : vérification visuelle, parcours interactif, multi-écrans, autostart, reboot, tout constat d'un exécutable que l'agent n'a pas le droit de lancer (motif OVERLAY récurrent, desktop_net). [desktop_net] : lancement de l'exe par l'Explorateur, menu tray, add-in dans Revit. [web_saas] : parcours dans le navigateur sur l'URL de prévisualisation, responsive, thèmes, états.

`checkpoint:decision` : DIFFÉRABLE seulement si une option par défaut est réversible dans la phase (aucune migration, aucune API publiée, aucun compte externe, aucun format persistant écrit chez l'utilisateur) ; le planner choisit ce défaut, l'écrit dans `<decision-default>`, et déclare un item `kind: decision-confirm` avec `blocks` = phases qui persisteront le choix. Sinon B1.

Question imprévue à l'exécution : le modèle principal classe lui-même avec la règle ci-dessus, une seule fois ; s'il juge bloquant il repose la question avec header `BLOQUANT` et le mod la laisse passer. Défaut en cas d'indécision : BLOQUANTE.

Décision réversible, décision irréversible : une décision est réversible si l'annuler dans la même phase ne coûte qu'un commit de code. Dès qu'elle écrit un schéma, un format de fichier chez l'utilisateur, un compte externe ou une API publiée, elle est irréversible et donc B1.

Interdits :
- classer différable pour éviter un arrêt alors que B1/B2 s'applique ;
- classer bloquant « par prudence » une simple confirmation visuelle ;
- convertir ou sauter un checkpoint de sa propre initiative (cas 06-04 et 20-05).

Tanguy peut requalifier depuis le panneau `/argos` ; l'override est inscrit dans le frontmatter de la file (`overrides_bloquant`).

## Syntaxe dans un PLAN.md [tous profils]

### Bloquant : tâche checkpoint GSD avec enfant `<blocking>`

Syntaxe GSD inchangée (`references/checkpoints.md`), plus un enfant obligatoire `<blocking kind="B1|B2|B3" consumer="…">`. `consumer` nomme ce qui consomme la réponse : un identifiant de tâche, un plan, une phase ou `publication`. Jamais vide.

Exemple B1, `checkpoint:human-verify` (exemple OVERLAY, desktop_net) :

```xml
<task type="checkpoint:human-verify" gate="blocking">
  <blocking kind="B1" consumer="43-04/T3, phase 44">Les heures relevées alimentent LUE-02.</blocking>
  <what-built>Relevé des heures d'exécution exposé dans l'onglet Diagnostic</what-built>
  <how-to-verify>
    1. Lancer Chronos-v3.5.0.exe par l'Explorateur
    2. Ouvrir Diagnostic, noter les trois heures affichées
  </how-to-verify>
  <resume-signal>Taper les trois heures au format HH:MM, séparées par des virgules</resume-signal>
</task>
```

Exemple B1, `checkpoint:decision` (exemple OVERLAY, desktop_net) :

```xml
<task type="checkpoint:decision" gate="blocking">
  <blocking kind="B1" consumer="phase 44">Le format persistant est écrit chez l'utilisateur.</blocking>
  <decision>Choisir le moteur de stockage</decision>
  <context>Un fichier par projet, lu au démarrage</context>
  <options>
    <option id="sqlite">…</option>
    <option id="json">…</option>
  </options>
  <resume-signal>Select: sqlite ou json</resume-signal>
</task>
```

Exemple B3, `checkpoint:human-action` planifié (geste connu au plan : secret à poser) [tous profils] :

```xml
<task type="checkpoint:human-action" gate="blocking">
  <blocking kind="B3" consumer="43-03/T2">La clé API n'a pas de CLI : seul l'humain peut la poser dans le coffre.</blocking>
  <action>Poser la clé API du fournisseur dans le gestionnaire de secrets du projet</action>
  <instructions>
    J'ai créé la variable attendue et le code qui la lit (tâche 1).
    Copier la clé depuis le tableau de bord du fournisseur dans le gestionnaire de secrets, nom exact dans la tâche 1.
  </instructions>
  <verification>La tâche 2 lit la variable et l'appel de test répond 200</verification>
  <resume-signal>Taper "done" quand la clé est posée</resume-signal>
</task>
```

Exemple B2, `checkpoint:human-verify` avant déploiement [web_saas] :

```xml
<task type="checkpoint:human-verify" gate="blocking">
  <blocking kind="B2" consumer="publication">La tâche suivante déploie en production sur Vercel.</blocking>
  <what-built>Parcours d'inscription et page de tarifs, déployés sur l'URL de prévisualisation</what-built>
  <how-to-verify>
    1. Ouvrir l'URL de prévisualisation donnée dans le SUMMARY de la tâche 2
    2. Jouer l'inscription avec un compte de test, vérifier l'e-mail de bienvenue en bac à sable
  </how-to-verify>
  <resume-signal>Taper "approved" pour déployer en production, ou décrire le problème</resume-signal>
</task>
```

Un plan qui contient une tâche checkpoint porte `autonomous: false` dans son frontmatter (`templates/phase-prompt.md:22`). C'est ce champ que l'horizon lit.

### Différable : bloc `<manual-items>` dans le plan qui construit la fonctionnalité

Un différable n'est JAMAIS une tâche checkpoint. Il est déclaré dans un bloc `<manual-items>` placé après `</tasks>`, dans un plan `autonomous: true`. Un item par ligne de vérification. Champs, dans cet ordre :

- `id` : `{phase}-D{n}`, n croissant dans la phase.
- `kind` : `verify` (constat pass/issue), `decision-confirm` (confirmer un défaut réversible pris), `action` (geste humain sans valeur consommée, exemple : épingler le raccourci, vider un cache).
- `source` : obligatoire. `{plan}/{tâche}` qui a construit ce que l'item vérifie (exemple `43-04/T2`), ou `{NN}-VERIFICATION.md` pour un item issu du vérificateur. Le planner le fournit, le mod le recopie tel quel.
- `titre` : une ligne.
- `where` : où regarder (exe, URL de prévisualisation, écran, commande).
- `do` : ce que fait l'humain. Ne jamais écrire `reason:` dans ce champ.
- `expected` : résultat attendu sur UNE ligne, sans retour à la ligne.
- `default` : obligatoire si `kind: decision-confirm`, absent sinon. Vaut l'`option` de la `<decision-default>` correspondante.
- `blocks` : `none`, ou ids de plans, de phases, ou `publication`, retenus si l'item échoue.
- `if_fail` : conduite en cas d'issue, par défaut `gap, /gsd:plan-phase N --gaps`. Ne jamais écrire `reason:` ici.

Exemple (exemple OVERLAY, desktop_net) :

```xml
<manual-items>
  <item id="43-D1" kind="verify" source="43-04/T2" blocks="none">
    <titre>Menu tray 3.5.0</titre>
    <where>Chronos-v3.5.0.exe lancé par l'Explorateur, clic droit icône tray</where>
    <do>Lancer l'exe, clic droit, compter les entrées</do>
    <expected>Menu à 6 entrées, DatePicker visible, pas de crash sous 8 s</expected>
    <if_fail>gap, /gsd:plan-phase 43 --gaps</if_fail>
  </item>
  <item id="43-D2" kind="decision-confirm" source="43-02/T1" default="sqlite" blocks="44">
    <titre>Choix moteur de stockage, défaut pris sqlite</titre>
    <where>43-02-PLAN.md, tâche 1</where>
    <do>Confirmer sqlite ou demander json</do>
    <expected>Confirmer sqlite ou demander json ; réversible, un fichier, aucune migration</expected>
    <if_fail>issue major, reprise par /gsd:plan-phase 43 --gaps</if_fail>
  </item>
</manual-items>
```

Exemple [web_saas], différable navigateur :

```xml
<manual-items>
  <item id="12-D1" kind="verify" source="12-02/T3" blocks="none">
    <titre>Tableau de bord responsive et thème sombre</titre>
    <where>URL de prévisualisation du déploiement, donnée dans 12-02-SUMMARY.md</where>
    <do>Ouvrir le tableau de bord à 375 px puis 1280 px, basculer le thème sombre</do>
    <expected>Aucun débordement horizontal, cartes empilées à 375 px, contraste lisible en sombre</expected>
    <if_fail>gap, /gsd:plan-phase 12 --gaps</if_fail>
  </item>
</manual-items>
```

Le mod extrait ce bloc à l'écriture du PLAN.md et crée ou fusionne `NN-HUMAN-UAT.md` (`source` et `default` y sont recopiés, voir le gabarit de `references/file-manuelle.md`). L'exécuteur ne touche pas à la file.

### Décision différée : `<decision-default>`

Quand une décision est différable, la tâche auto qui la prend porte un enfant `<decision-default>` :

```xml
<task type="auto">
  <name>Task 1: Brancher le stockage</name>
  <decision-default item="43-D2" option="sqlite">Réversible : un fichier, aucune migration, aucun format écrit chez l'utilisateur avant la phase 44.</decision-default>
  <action>…implémenter sqlite, marquer « provisoire » dans le SUMMARY…</action>
  …
</task>
```

L'attribut `item` cite l'item `decision-confirm` correspondant. L'exécuteur applique l'option par défaut et écrit « provisoire : {id} » dans le SUMMARY.

## Règle de vagues [tous profils]

- Un plan bloquant (`autonomous: false`) va dans la vague la plus tardive possible de la phase.
- Plusieurs bloquants dans une phase : un plan par bloquant, vagues croissantes dans l'ordre de consommation des réponses ; l'horizon s'arrête au premier (vague minimale).
- Un plan bloquant est minimal : préparation, le checkpoint, puis les seules tâches qui consomment la réponse. Tout ce qui ne dépend pas de la réponse va dans un plan autonome de vague inférieure.
- Les tâches qui précèdent le checkpoint dans le plan bloquant sont idempotentes : rejouées, elles produisent le même résultat. Motif : la reprise spawne un exécuteur de continuation neuf (voir `references/file-manuelle.md`).
- Un plan autonome placé en vague supérieure ou égale à celle d'un plan bloquant doit en dépendre (`depends_on`). Règle unique : rejeté par le gsd-plan-checker (contrôle 4) ; le planner déplace le plan en vague inférieure ou ajoute la dépendance avant de resoumettre. Le mod `argos` n'émet qu'un avertissement, il ne corrige pas.
- Les `<manual-items>` vont dans les plans autonomes, jamais dans un plan bloquant.
- L'horizon de l'auto s'arrête à la première vague contenant un plan `autonomous: false` sans SUMMARY. Tout ce qui précède s'exécute sans arrêt.

## Les cinq contrôles du gsd-plan-checker [tous profils]

Le checker rejette le plan si un contrôle échoue. Message dans le rapport de vérification, un item par échec.

1. Chaque `<task type="checkpoint:*">` porte un enfant `<blocking kind="B1|B2|B3" consumer="…">` et `consumer` est non vide.
2. Aucun différable n'est une tâche checkpoint. Un `checkpoint:human-verify` dont le `<blocking>` ne cite aucun consommateur réel (B1) ni aucune étape irréversible aval (B2) ni geste de mains humaines (B3) est un différable mal classé : à déplacer en `<manual-items>`.
3. Chaque `<item>` de `<manual-items>` a un `expected` sur une seule ligne, non vide, et un `source` non vide.
4. Vagues respectées : un plan `autonomous: false` est en vague maximale parmi ses dépendants ; aucun plan autonome en vague supérieure ou égale à un plan bloquant sans en dépendre (rejet : le planner déplace le plan ou ajoute la dépendance, puis resoumet) ; plusieurs bloquants ont chacun leur plan en vagues croissantes ; les tâches pré-checkpoint du plan bloquant sont idempotentes.
5. `blocks` est renseigné sur chaque item (`none` ou ids). Un item `decision-confirm` a un `blocks` non `none`, un `default` et une `<decision-default>` correspondante dans une tâche auto dont l'`option` est égale au `default`.

Contrôle supplémentaire [web_saas] : un item `verify` qui précède une tâche aval de déploiement ou de migration a `blocks: publication` au minimum, sinon il est B2 et doit devenir un checkpoint.

## Interdits de l'exécuteur [tous profils]

- Ne jamais convertir un checkpoint en tâche auto, ni le sauter, ni le « considérer validé » sur accord implicite.
- Ne jamais appliquer « ⚡ Auto-approved » ni « ⚡ Auto-selected », quelle que soit la valeur de `workflow.auto_advance` ou `workflow._auto_chain_active` (`agents/gsd-executor.md:233-236`, `workflows/execute-phase.md:385-386`). ARTHEMIS force ces deux clés à `false` par `gsd-tools config-set` à l'ouverture du cycle. Si l'exécuteur les lit `true` malgré tout, il rend quand même le checkpoint en `## CHECKPOINT REACHED` (`agents/gsd-executor.md:258`).
- Un checkpoint est toujours rendu au format `checkpoint_return_format` : Completed Tasks avec hashes, Current Task, Checkpoint Details, Awaiting.
- Un plan sans checkpoint s'exécute sans question. Toute question imprévue passe par la règle de classification, une seule fois.
- Ne jamais inventer un résultat humain. Une vérification différée est consignée, pas simulée.
- Ne jamais écrire dans `NN-HUMAN-UAT.md` depuis un exécuteur : les exécuteurs tournent en worktree (`workflows/execute-phase.md:230`) et le fichier serait hors du dépôt principal. L'exécuteur note « différé : {id} » dans son SUMMARY.

## Bloc fixe « ## HORIZON ATTEINT » [tous profils]

Quand plus rien n'est automatisable avant le prochain bloquant, le modèle principal termine sa réponse par ce bloc, mot pour mot, valeurs remplacées. Le mod le reconnaît par son titre et n'applique aucun rappel dessus.

```markdown
## HORIZON ATTEINT

Bloquant : {plan} tâche {n} ({kind}) : {titre}
Signal de reprise : {resume_signal}
Phase : {phase} vague {wave_bloquante} | ARTHEMIS : {phase_pipeline}/{phase_status}

Items en file :
- {id} {kind} : {titre} | blocks {blocks} | {chemin NN-HUMAN-UAT.md}
- …

Tâches ARTHEMIS différées :
- arthemis:{checkpoint} : {titre} | preuve attendue {preuve}
- …

Reprise : bouton Débloquer du panneau /argos, ou saisir la réponse au bloquant.
```

Règles :
- `{kind}` prend une valeur de `kind_bloquant` du schéma d'état : `human-verify`, `decision`, `human-action`, `question`, `authentification`.
- `{phase_status}` vaut `attente_humaine` quand le bloc est émis.
- La section « Tâches ARTHEMIS différées » liste les points d'arrêt de l'orchestrateur passés en `differe: true` dans `.arthemis/state.json` (`checkpoints.plan_design`, `checkpoints.triage`, `checkpoints.roadmap`). Elle est vide, et écrite « - aucune », quand rien n'est différé. [web_saas] : `checkpoints.cadrage` n'y figure jamais, il est bloquant.
- `checkpoints.go_publication` n'y figure jamais : toujours bloquant.
- Le bloc n'est jamais émis par un sous-agent, uniquement par le modèle principal.
