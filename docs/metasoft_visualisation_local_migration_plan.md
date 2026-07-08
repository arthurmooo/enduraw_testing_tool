# Plan migration locale - Visualisation MetaSoft

Date: 2026-07-08

Objectif: migrer les fonctionnalités de visualisation MetaSoft développées dans la branche dashboard `feature/testing-tools-metasoft-p0` vers l'app locale Python `enduraw_testing_tool`, en conservant le flux existant de Valentin: sessions locales, profils, XML matchés, export JSON local.

Ce document est un plan. Il ne déclenche aucune implémentation.

## Résumé exécutif

La cible produit ne doit pas être le dashboard online pour ce P0. Les XML MetaSoft peuvent être lourds, les calculs et graphes interactifs peuvent consommer de la RAM/CPU, et les coachs doivent pouvoir utiliser l'outil sans terminal.

La bonne trajectoire est une app locale cliquable:

```text
Enduraw Testing Tool local
  Sessions / Profils / XML / Matching / Export existants
  + moteur MetaSoft enrichi
  + vue graphes interactive locale
  + synchronisation marqueurs -> profil local
  + export JSON Valentin existant enrichi
```

Recommandation technique:

- garder Python pour le stockage local, parsing XML, calculs, export JSON, packaging;
- ajouter une UI web locale pour les graphes interactifs;
- viser une fenêtre app intégrée via `pywebview` si le packaging reste simple;
- garder un fallback navigateur local si `pywebview` crée trop de complexité Mac/Windows.

## Suivi d'implémentation

### 2026-07-08 - tranche `feature/metasoft-local-core`

Décisions prises:

- première tranche limitée au coeur local parser/analyse/export;
- pas d'UI React, pas de pywebview, pas de packaging dans cette tranche;
- branche dédiée créée dans `enduraw_testing_tool`: `feature/metasoft-local-core`;
- parser XML existant renforcé au lieu d'ajouter un second parseur concurrent;
- compatibilité conservée avec les clés historiques `filename_data`,
  `patient_data`, `summary_data` et `measurements`;
- payload normalisé ajouté sous `metasoft_parsed` et analyse sous
  `metasoft_analysis`;
- analyse EC placée dans `src/core/metasoft_analysis.py`, sans I/O ni BDD;
- export Valentin continue de produire le JSON strict existant;
- les graphes exportés utilisent les points normalisés si présents, sinon les
  mesures historiques;
- les seuils restent issus du profil coach, pas de déduction automatique depuis
  les courbes;
- identité et poids XML servent seulement de fallback export si le profil local
  est incomplet.

Validations faites:

- tests unitaires ciblés sur fixture XML synthétique;
- smoke read-only sur les 3 XML réels fournis;
- compilation Python;
- `git diff --check`;
- nettoyage des caches générés par `compileall`.

## Contraintes produit

- Utilisateurs non tech: Thibaut sur Mac, Kylian sur Windows.
- Lancement cible: icône / exécutable cliquable, pas de terminal.
- Tests importants sur sportifs professionnels: ne pas dégrader le signal pour gagner artificiellement en performance.
- XML worst-case cible: 20 MB.
- Session réelle: lieu + date, potentiellement 30 à 40 tests dans une journée.
- Mongo lookup à conserver, mais l'app doit rester utilisable sans Mongo.
- Aucun push BDD depuis l'app: export JSON local envoyé à Valentin comme aujourd'hui.
- Si un marqueur existe déjà dans le profil, demander confirmation avant écrasement.
- Lissage ajustable requis côté lecture, non destructif et uniquement visuel.

## État actuel - app locale Valentin

Repo: `/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool`

Entrée:

- `main.py` charge `.env`, ajoute `src/` au path, lance `TCPDataProcessorSession`.
- `src/main_session.py` contient l'app desktop CustomTkinter.
- `README.md` documente le build PyInstaller Windows.
- `docs/GUIDE_MAC.md` documente un lancement Mac via script `.command`, mais pas encore un `.app` packagé.

Dépendances actuelles:

- `customtkinter`
- `pyinstaller`
- `pymongo`
- `pydantic`
- `email-validator`
- `matplotlib`

Stockage local existant:

```text
sessions/
  <date_lieu>/
    session.json
    profiles/*.json
    xml/*.xml
    matches.json
    output/*.json
```

Modules existants à conserver:

- `src/core/session_manager.py`
  - crée/charge/supprime sessions;
  - sauvegarde profils;
  - importe XML par copie locale;
  - gère matches profil/XML;
  - écrit outputs JSON.
- `src/core/profile_template.py`
  - structure locale des profils.
- `src/ui/tabbed_form.py`
  - formulaire profil et mesures.
- `src/core/data_transformer.py`
  - fusion XML + profil en JSON Valentin.
- `src/core/mongo_service.py`
  - lookup Mongo read-only par email.
- `src/core/protocol_store.py`
  - protocoles réutilisables.

Flux utilisateur existant:

1. Créer/ouvrir une session.
2. Créer/remplir un profil local.
3. Pré-remplir éventuellement depuis Mongo par email.
4. Importer un ou plusieurs XML dans la session.
5. Matcher profil + XML.
6. Exporter un match ou tous les matches en JSON.

Points à préserver:

- Le concept de session lieu/date.
- Les profils JSON locaux.
- Le matching explicite profil/XML.
- L'export batch.
- Le dossier `output/` par session.
- Le lookup Mongo optionnel.
- La logique d'export actuelle, tant qu'elle reste compatible avec Valentin.

Limites actuelles:

- Le parser XML ne respecte pas `ss:Index`; risque de décalage de colonnes dans certains Spreadsheet XML.
- Le parsing filename est trop strict pour les noms composés.
- Les graphes export actuels sont limités aux graphes JSON historiques, pas à une visualisation interactive.
- Pas de moteur d'analyse MetaSoft riche: phases, paliers vitesse, EC, warnings.
- Pas de tests automatisés.
- UI CustomTkinter adaptée aux formulaires, pas aux interactions graphiques lourdes.

## État actuel - prototype dashboard MetaSoft

Repo source: `/Users/arthurmo/Developer/Enduraw/code/dashboard`

Branche source: `feature/testing-tools-metasoft-p0`

Important: cette branche contient des fichiers non commités. La migration doit lire le workspace local, pas seulement GitHub.

Backend source:

- `backend/coaching/metasoft_parser.py`
- `backend/coaching/metasoft_analysis.py`
- `backend/coaching/metasoft_export.py`
- tests dédiés dans `backend/tests/test_metasoft_*.py`

Frontend source:

- `frontend/src/pages/coach/CoachMetaSoftTestingPage.tsx`
- `frontend/src/components/coach-metasoft/MetaSoftChart.tsx`
- `frontend/src/components/coach-metasoft/MetaSoftUploadToolbar.tsx`
- `frontend/src/components/coach-metasoft/MarkerPanel.tsx`
- `frontend/src/components/coach-metasoft/AnalysisExportSection.tsx`
- `frontend/src/components/coach-metasoft/chartUtils.ts`
- `frontend/src/components/coach-metasoft/markerUtils.ts`
- `frontend/src/components/coach-metasoft/graphConfig.ts`
- `frontend/src/components/coach-metasoft/downloadUtils.ts`
- `frontend/src/types/metasoft.ts`
- `frontend/src/services/metasoftService.ts`

Features validées côté dashboard:

- Upload XML par bouton.
- Drag & drop XML.
- Validation extension `.xml`.
- Limite actuelle dashboard 15 MB; cible app locale à passer à 20 MB.
- Parsing Spreadsheet XML avec respect `ss:Index`.
- Parsing filename compatible noms composés.
- Extraction poids même avec suffixe unité type `68,0 kg`.
- Extraction métriques:
  - `V'O2`
  - `V'O2/kg`
  - `V'CO2`
  - `FC`
  - `V'E`
  - `VT`
  - `BF`
  - `RER`
  - `v`
  - `PetO2`
  - `PetCO2`
  - `DE`
  - `DECHO`
  - `DEFAT`
  - `DEPRO`
  - `V'E/V'O2`
  - `V'E/V'CO2`
- Unités et labels source conservés.
- Points normalisés avec `t_seconds`, phase, marqueur, values, raw.
- Phases fiables depuis MetaSoft.
- Paliers vitesse en background derrière les courbes.
- Labels de vitesse en background pour segments suffisamment longs.
- 9 graphes configurés.
- Séries manquantes affichées explicitement.
- Toggle de séries par graphe.
- Fullscreen par graphe.
- Zoom Plotly persistant.
- Double-clic reset zoom.
- Lissage global en secondes, désactivable à `0s`.
- Lissage non appliqué à `speed_kmh` pour préserver les paliers.
- Curseur live avec valeurs au point.
- Proposition de marqueur au clic.
- Choix marqueur `SV1`, `SV2`, `VO2max`.
- Mode `Ligne` ou `Range`.
- Durée de range saisissable.
- Fenêtre par défaut autour marqueur.
- Moyenne des valeurs sur fenêtre officielle.
- Drag du centre de fenêtre.
- Drag des bornes début/fin.
- Clic droit suppression marqueur.
- VMA traitée comme marqueur à part via valeur vitesse.
- Tableau marqueurs.
- Edition manuelle début/fin en horloge.
- Warnings backend visibles.
- EC par palier d'échauffement.
- Masquage de paliers EC dans le graphe EC.
- Export CSV audit.
- Export JSON strict Valentin.
- Validation bloquante des champs requis.

## Mapping dashboard -> app locale

### 1. Parsing XML

Source dashboard:

- `backend/coaching/metasoft_parser.py`

Cible app locale:

- remplacer ou enrichir `src/utils/xml_parser.py`.

Décision:

- Ne pas garder deux parsers divergents.
- Introduire un parser MetaSoft normalisé dans l'app locale, idéalement `src/core/metasoft_parser.py`.
- Garder l'ancien `TCPXmlParser` comme façade de compatibilité si `DataTransformer` en dépend encore.

À migrer:

- respect `ss:Index`;
- métriques canoniques;
- unités;
- noms composés;
- poids texte avec unité;
- warnings de métriques manquantes;
- points normalisés.

### 2. Analyse MetaSoft

Source dashboard:

- `backend/coaching/metasoft_analysis.py`

Cible app locale:

- nouveau module `src/core/metasoft_analysis.py`.

À migrer:

- `build_phase_segments`;
- `detect_warmup_stages`;
- filtrage paliers courts;
- baseline repos;
- EC en `J/kg/m`;
- `VO2`/`VCO2` en `ml/min`;
- `VCO2` natif sinon `VO2 * RER`;
- pas de fallback via `V'E/(V'E/VCO2)`;
- warning sur cohérence ventilatoire;
- warning vitesse nulle / masse absente / repos absent;
- `DE*` natif en `kcal/h`.

À adapter:

- la masse doit venir en priorité du profil local si le XML ne la donne pas;
- les warnings doivent être visibles dans la vue web locale;
- l'analyse doit pouvoir être recalculée après changement profil si poids modifié.

### 3. Export JSON Valentin

Sources:

- dashboard: `backend/coaching/metasoft_export.py`;
- app actuelle: `src/core/data_transformer.py`.

Cible:

- garder `DataTransformer` comme source principale du JSON historique;
- l'enrichir pour accepter des marqueurs calculés depuis la vue MetaSoft;
- éviter d'introduire un deuxième exporteur concurrent.

Décision:

- Le JSON final doit sortir du flux app locale existant.
- Les marqueurs de la vue MetaSoft doivent être synchronisés vers le profil local dans `stress_test_results`.
- `DataTransformer` continue à produire le JSON, mais avec les champs automatiquement remplis.

Mapping marqueurs -> profil:

```text
SV1.values.fc           -> stress_test_results.thresholds.sv1.hr_bpm
SV1.values.speed_kmh    -> stress_test_results.thresholds.sv1.pace_km_h
SV1.values.vo2_ml_kg_min -> stress_test_results.thresholds.sv1.vo2_ml_kg_min

SV2.values.fc           -> stress_test_results.thresholds.sv2.hr_bpm
SV2.values.speed_kmh    -> stress_test_results.thresholds.sv2.pace_km_h
SV2.values.vo2_ml_kg_min -> stress_test_results.thresholds.sv2.vo2_ml_kg_min

VO2_max.values.fc       -> stress_test_results.max_hr
VO2_max.values.vo2_ml_kg_min -> stress_test_results.measured_vo2max

VMA.values.speed_kmh    -> stress_test_results.vma
```

Règle d'écrasement:

- si le champ cible est vide: remplir automatiquement;
- si le champ cible contient déjà une valeur différente: demander confirmation;
- si le coach refuse: garder l'existant et conserver le marqueur seulement dans l'analyse temporaire.

### 4. UI graphes

Source dashboard:

- `MetaSoftChart.tsx`
- `chartUtils.ts`
- `markerUtils.ts`
- `graphConfig.ts`
- `MetaSoftUploadToolbar.tsx`
- `MarkerPanel.tsx`
- `AnalysisExportSection.tsx`

Cible app locale:

- UI web locale embarquée.

Deux options:

#### Option A - pywebview intégré

```text
CustomTkinter app
  -> bouton "Analyse MetaSoft"
  -> ouvre fenêtre pywebview
  -> charge bundle React local
  -> communique avec Python via API JS / HTTP local
```

Avantages:

- expérience "vraie app";
- pas de navigateur visible;
- plus proche de l'icône actuelle.

Risques:

- packaging Mac/Windows à valider;
- debug plus pénible;
- dépendance `pywebview` à tester sur machines coachs.

#### Option B - navigateur local

```text
CustomTkinter app
  -> démarre serveur local 127.0.0.1
  -> ouvre Safari/Chrome sur une page locale
```

Avantages:

- plus robuste;
- plus simple à debugger;
- Plotly/React se comporte comme dans le dashboard;
- fallback excellent si pywebview pose problème.

Risques:

- moins "app native";
- l'utilisateur voit un navigateur.

Recommandation:

- viser Option A en cible;
- concevoir l'architecture pour basculer en Option B sans réécrire;
- faire un spike packaging pywebview très tôt.

### 5. Communication Python <-> UI web

Ne pas envoyer les XML au serveur dashboard. Tout reste local.

Deux designs possibles:

#### API locale HTTP

Python lance un petit serveur local:

```text
GET  /api/session/current
GET  /api/matches
POST /api/metasoft/analyze
POST /api/metasoft/markers/sync
POST /api/export/preview
```

Avantages:

- modèle proche du dashboard;
- React réutilisable facilement;
- fonctionne avec pywebview et navigateur.

Inconvénient:

- ajouter une dépendance serveur locale (`fastapi` ou `flask`).

#### Bridge pywebview

React appelle directement des méthodes Python exposées par pywebview.

Avantages:

- pas de serveur HTTP;
- plus "desktop".

Inconvénients:

- moins portable vers navigateur fallback;
- plus couplé à pywebview.

Recommandation:

- commencer avec API locale HTTP minimale.
- Exposer uniquement `127.0.0.1`.
- Démarrer/arrêter avec l'app.
- Cela garde le fallback navigateur trivial.

### 6. Intégration dans le flux existant

Point d'entrée UI proposé:

- dans `XML Matching`, sur chaque association profil/XML:
  - bouton actuel `Exporter`;
  - nouveau bouton `Analyser`;
  - bouton `Exporter tout` inchangé.

Flux cible pour un match:

1. Coach ouvre session.
2. Coach sélectionne/matche un profil et un XML.
3. Coach clique `Analyser`.
4. La vue MetaSoft locale s'ouvre sur ce XML + profil.
5. Python parse/analyse.
6. UI affiche les graphes.
7. Coach place/ajuste `SV1`, `SV2`, `VO2max`, `VMA`.
8. Coach clique `Reporter au profil`.
9. Si champs existants différents: confirmation.
10. Profil local sauvegardé.
11. Export JSON utilise le profil mis à jour.

Flux batch:

- Pour une session de 30-40 tests, ne pas charger/analyser tous les XML simultanément.
- Garder le batch export actuel.
- Ajouter un statut par match:
  - non analysé;
  - analysé;
  - marqueurs reportés;
  - exporté.
- En P0, analyse unitaire suffisante; batch analyse seulement si nécessaire plus tard.

## Plan d'implémentation recommandé

### Phase 0 - Préparation

But: figer le contrat et éviter les régressions.

Actions:

- Créer une branche dédiée dans `enduraw_testing_tool`.
- Copier les XML de test localement hors Git.
- Ajouter un dossier de tests unitaires minimal.
- Ajouter fixtures synthétiques non sensibles.
- Documenter que `sessions/`, XML réels et outputs ne sont pas commités.

Checks:

- `python -m compileall main.py src`
- tests parser/analysis/export.

### Phase 1 - Moteur MetaSoft local

But: intégrer le coeur Python du dashboard dans l'app locale.

Fichiers probables:

- `src/core/metasoft_parser.py`
- `src/core/metasoft_analysis.py`
- `src/core/metasoft_markers.py`
- `src/core/metasoft_export_adapter.py`
- `tests/test_metasoft_parser.py`
- `tests/test_metasoft_analysis.py`
- `tests/test_metasoft_markers.py`

Travail:

- migrer parser robuste;
- migrer analyse EC;
- créer calcul marqueurs côté Python pour éviter logique métier uniquement frontend;
- adapter format vers `DataTransformer` / profil local.

Règle importante:

- Les calculs officiels doivent être côté Python.
- Le lissage UI ne doit jamais modifier les valeurs exportées.
- Les marqueurs utilisent les points bruts dans la fenêtre, pas la série lissée.

### Phase 2 - API locale

But: permettre à une UI web locale de parler au moteur sans serveur externe.

Option recommandée:

- ajouter `fastapi` + `uvicorn` ou `flask`.

Endpoints locaux minimaux:

```text
GET  /api/health
GET  /api/session
GET  /api/match/{match_id}
POST /api/metasoft/analyze
POST /api/metasoft/markers/preview
POST /api/metasoft/markers/apply
GET  /api/export/preview/{match_id}
```

Contraintes:

- bind uniquement `127.0.0.1`;
- port dynamique si port occupé;
- pas d'upload réseau externe;
- analyse d'un seul XML à la fois;
- libérer les grosses structures quand la fenêtre se ferme.

### Phase 3 - UI React locale

But: réutiliser le prototype dashboard sans dépendre du dashboard.

Créer probablement:

```text
web/
  package.json
  src/
    MetaSoftLocalApp.tsx
    components/metasoft/*
    types/metasoft.ts
```

À reprendre du dashboard:

- `MetaSoftChart.tsx`
- `chartUtils.ts`
- `markerUtils.ts`
- `graphConfig.ts`
- `CursorRail.tsx`
- `MarkerPanel.tsx`
- morceaux utiles de `AnalysisExportSection.tsx`

À retirer/adaper:

- routing dashboard;
- auth;
- `apiService`;
- layout dashboard;
- export JSON direct download si l'app Python gère l'output;
- classes Tailwind si le build local ne garde pas Tailwind.

Décision UI:

- Le look peut rester perfectible au début.
- Priorité: interactions, stabilité, performance, exactitude.

### Phase 4 - Synchronisation marqueurs -> profil

But: que les clics graphes remplacent la saisie manuelle actuelle quand le coach le souhaite.

Implémenter:

- preview des valeurs à reporter;
- comparaison avec profil actuel;
- confirmation si conflit;
- sauvegarde dans `profiles/*.json`;
- refresh du formulaire CustomTkinter si la fenêtre reste ouverte;
- statut `markers_applied` dans match metadata ou fichier annexe.

Stockage recommandé:

Ne pas surcharger `matches.json` en P0 si ça complique.

Option simple:

```text
sessions/<session>/analysis/
  <profile>__<xml>.metasoft.json
```

Contenu:

- marqueurs;
- fenêtres;
- warnings;
- hash/mtime XML;
- version moteur.

Puis le profil contient seulement les champs métiers nécessaires à l'export.

### Phase 5 - Packaging cliquable

But: Thibaut/Kylian lancent par icône.

Windows:

- PyInstaller `.exe`;
- inclure bundle web;
- inclure ressources;
- tester sans Python installé.

Mac:

- PyInstaller `.app` ou équivalent;
- tester Gatekeeper/quarantine;
- vérifier lancement double-clic;
- éventuellement fournir `.command` fallback.

Ne pas viser packaging parfait avant d'avoir validé:

- pywebview vs navigateur;
- perf gros XML;
- écriture profils;
- export JSON final.

## Performance

Contraintes:

- XML jusqu'à 20 MB.
- 30-40 XML dans une session.
- PC Windows modeste.

Principes non négociables:

- Ne charger/analyser qu'un XML à la fois.
- Ne pas pré-parser toute la session.
- Ne pas garder plusieurs analyses lourdes en mémoire.
- Ne pas recalculer les moyennes/EC à chaque mouvement UI.
- Ne pas lisser en modifiant les données brutes.
- Ne pas baser l'export sur données décimées.

Optimisations à intégrer dès le départ:

- Parser XML vers structure compacte.
- Séries numériques sous listes simples.
- Pré-calculer les segments vitesse/phases une fois.
- Moyennes de fenêtre via préfix sums par métrique si le drag devient coûteux.
- Lissage glissant O(n), pas O(n²).
- Décimation uniquement pour rendu si un XML est trop dense.
- Rendu Plotly limité aux graphes visibles.
- Fullscreen un graphe à la fois.
- Pas de WebGL tant que SVG reste assez fluide; tester avant d'ajouter `scattergl`.

Décimation:

- Autorisée pour affichage seulement.
- Interdite pour calculs officiels.
- L'UI doit pouvoir afficher "rendu optimisé" si on décime.

Lissage:

- Slider conservé.
- `0s` = signal brut.
- Lissage visuel seulement.
- Vitesse non lissée.
- Marqueurs calculés sur points bruts de la fenêtre.

## Risques et réponses

### Risque: pywebview complique le packaging

Réponse:

- architecture API locale compatible navigateur;
- fallback navigateur accepté en V1 si besoin.

### Risque: app trop lourde avec React + Plotly

Réponse:

- bundle local unique;
- lazy render des graphes;
- analyse unitaire;
- tests sur XML 20 MB avant enrichissements visuels.

### Risque: divergence entre export app et export dashboard

Réponse:

- ne pas maintenir deux exports métier;
- faire de `DataTransformer` la sortie officielle app;
- seulement synchroniser les champs profil depuis les marqueurs.

### Risque: écraser valeurs saisies par Thibaut

Réponse:

- confirmation si champ déjà rempli;
- afficher ancien/nouveau;
- possibilité d'annuler.

### Risque: Mongo URI locale sensible

Réponse:

- conserver `.env` / `mongo_config.json` ignorés;
- ne jamais commiter;
- à terme, éviter de sauvegarder l'URI en clair si distribution plus large.

### Risque: parsing ancien et nouveau divergent

Réponse:

- remplacer progressivement l'ancien parser par le parser robuste;
- tests sur XML réels;
- garder une façade compat pour `DataTransformer`.

## Décisions proposées

- Oui: migrer vers l'app locale.
- Oui: garder sessions/profils/matching/export existants.
- Oui: ajouter une vue interactive MetaSoft locale.
- Oui: préserver toutes les features de clic/zoom/lissage/range validées dans le dashboard.
- Oui: demander confirmation avant écrasement profil.
- Oui: Mongo lookup reste optionnel et read-only.
- Non: ne pas faire du dashboard online la cible production P0.
- Non: ne pas refaire les graphes avancés en pur CustomTkinter/Matplotlib.
- Non: ne pas pré-analyser toute une session de 40 XML.

## Questions restantes avant code

- Confirmer si la première V1 peut s'ouvrir dans le navigateur local si pywebview bloque.
- Obtenir un XML proche du pire cas 20 MB pour benchmark.
- Obtenir une session réelle ou anonymisée pour valider le flux 30-40 tests.
- Confirmer le format exact souhaité pour stocker les analyses locales hors profil.
- Confirmer avec Valentin que l'enrichissement de `DataTransformer` est préférable à un nouvel exporteur.

## Premier chantier recommandé

Le premier chantier ne doit pas être l'UI.

Ordre recommandé:

1. Créer branche dédiée dans `enduraw_testing_tool`.
2. Migrer parser/analyse MetaSoft côté Python avec tests.
3. Ajouter l'adapter marqueurs -> profil.
4. Ajouter un mini endpoint local ou bridge pour un XML matché.
5. Brancher la vue React locale.
6. Tester perf sur gros XML.
7. Packager.

Ce séquencement évite de construire une belle interface sur un moteur fragile.
