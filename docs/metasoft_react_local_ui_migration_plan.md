# MetaSoft React local UI - plan de migration

Date: 2026-07-08

Document de plan/audit uniquement. Aucun code applicatif n'est modifie par ce
document. Aucun appel BDD, aucune ecriture prod, aucun stage, commit ou push.

## Objectif

Migrer l'app Python locale `enduraw_testing_tool` vers une UI React locale pour
la lecture MetaSoft, sans perdre les garanties deja posees cote Python:
parsing XML, calculs officiels, sessions/profils locaux, report profil, export
JSON Valentin et sidecar audit.

La cible n'est pas un mini-dashboard online. C'est une app locale:

```text
CustomTkinter shell existant
  Sessions / Profils / XML / Matching / Export batch
  Bouton Analyser
    lance un serveur local Python 127.0.0.1
    ouvre une UI React locale dans navigateur
    option webview seulement apres validation packaging

Python reste source de verite
  XML -> metasoft_parsed -> metasoft_analysis
  selections UI -> marqueurs officiels Python
  marqueurs officiels -> profil local
  profil + XML + marqueurs -> JSON strict + sidecar audit
```

## 1. Etat actuel verifie

### Git et worktrees

Repo cible:
`/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool`

Branche locale verifiee:
`feature/metasoft-react-local-ui`.

Worktree deja sale avant ce plan:

- `run.sh` modifie.
- `src/core/data_transformer.py` modifie.
- `src/main_session.py` modifie.
- `src/ui/app_tabs.py` modifie.
- `src/utils/xml_parser.py` modifie.
- `docs/metasoft_local_ui_export_execution_plan.md` non suivi.
- `docs/metasoft_visualisation_local_migration_plan.md` non suivi.
- `src/core/metasoft_analysis.py` non suivi.
- `src/core/metasoft_audit_export.py` non suivi.
- `src/core/metasoft_markers.py` non suivi.
- `src/ui/metasoft_analysis_window.py` non suivi.
- `src/ui/metasoft_graphs.py` non suivi.
- `tests/` non suivi.

Ces changements sont du contexte utilisateur. Ne rien revert.

Dashboard source:
`/Users/arthurmo/Developer/Enduraw/code/dashboard`

Branche verifiee:
`feature/testing-tools-metasoft-p0`.

Worktree dashboard sale, notamment:

- `backend/activities/router.py` modifie: contrainte explicite, ne pas toucher.
- fichiers MetaSoft backend/frontend non suivis ou modifies.

Dashboard trainer tools:
`/Users/arthurmo/Developer/Enduraw/code/dashboard-trainer-tools`

Etat verifie:
`HEAD (no branch)`, avec `backend/.venv/` et `frontend/node_modules` non
suivis. Pas de brique MetaSoft plus utile que le dashboard principal; reference
secondaire seulement pour structure Vite si besoin.

### App locale actuelle

Repo:
`/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool`

Stack documentee:

- UI desktop: `customtkinter`.
- Graphes actuels: `matplotlib`.
- Packaging Windows: `pyinstaller`.
- Dependances actuelles: `customtkinter`, `pyinstaller`, `pymongo`,
  `pydantic`, `email-validator`, `matplotlib`.
- Stockage local:

```text
sessions/
  <date_lieu>/
    session.json
    profiles/*.json
    xml/*.xml
    matches.json
    output/*.json
```

Flux conserve:

1. Creer/ouvrir session.
2. Creer/remplir profil local.
3. Lookup Mongo optionnel en lecture.
4. Importer XML.
5. Matcher profil/XML.
6. Exporter un match ou tous les matches en JSON local.

### Modules Python MetaSoft existants

Modules verifies dans l'app locale:

- `src/utils/xml_parser.py`
  - lit Spreadsheet XML MetaSoft;
  - respecte `ss:Index`;
  - conserve le contrat historique `filename_data`, `patient_data`,
    `measurements`;
  - ajoute `metasoft_parsed`;
  - labels normalises: `V'O2`, `V'O2/kg`, `V'CO2`, `FC`, `V'E`, `VT`,
    `BF`, `RER`, `v`, `PetO2`, `PetCO2`, `DE`, `DECHO`, `DEFAT`,
    `DEPRO`, `V'E/V'O2`, `V'E/V'CO2`;
  - ne reconstruit pas les metriques physiologiques absentes.
- `src/core/metasoft_analysis.py`
  - construit phases;
  - detecte paliers d'echauffement;
  - calcule baseline repos;
  - calcule EC en `J/kg/m`;
  - utilise `V'CO2` natif si present, sinon fallback explicite
    `VO2 * RER`;
  - garde les warnings data.
- `src/core/metasoft_markers.py`
  - officialise les marqueurs depuis points XML bruts;
  - mode point: point XML le plus proche;
  - mode range: moyenne inclusive des points bruts;
  - mapping profil `SV1`, `SV2`, `VO2_max`, `VMA`;
  - n'utilise jamais lissage, interpolation ou decimation.
- `src/core/metasoft_audit_export.py`
  - construit sidecar `.metasoft_audit.json`;
  - inclut sources, unites, warnings, EC, marqueurs officiels;
  - ne modifie pas le JSON Valentin.
- `src/core/data_transformer.py`
  - reste le transformeur JSON strict;
  - seuils issus du profil local;
  - graphes exportes depuis points normalises si presents;
  - aggregation export 15 s;
  - aucun lissage exporte.
- `src/core/session_manager.py`
  - source canonique pour lecture/ecriture locale session;
  - helpers existants: `get_profile`, `update_profile`, `get_xml_path`,
    `save_output`.
- `src/main_session.py`
  - possede deja `_analyze_match`;
  - export unitaire et batch sauvent deja JSON + audit sidecar.
- `src/ui/app_tabs.py`
  - `MatchListItem` possede deja un bouton `Analyser`.
- `src/ui/metasoft_analysis_window.py`
  - V1 CustomTkinter MetaSoft deja presente dans le worktree;
  - utile comme reference fonctionnelle, mais UI jugee insuffisante.
- `src/ui/metasoft_graphs.py`
  - config locale des graphes;
  - helpers purs de lissage visuel et series.

Tests locaux verifies en lecture:

- `tests/test_metasoft_local_core.py`
- `tests/test_metasoft_audit_export.py`
- `tests/test_metasoft_main_session_export.py`
- `tests/test_metasoft_ui_helpers.py`

### XML reel inspecte

Fichier:
`/Users/arthurmo/Downloads/TCP__VAN DER VEEN_Noor_2026.06.10_12.38.06_.xml`

Constats via parser local:

- taille: `5,846,957` octets, environ `5.6 MB`;
- points normalises: `1742`;
- athlete XML: `VAN DER VEEN Noor`;
- poids XML: `68.0 kg`;
- test: `2026-06-10T12:38:06`;
- phases: `Repos`, `Echauffement`, `Exercice`, `Retablissement`;
- paliers d'echauffement detectes: `9.0`, `10.0`, `11.0`, `7.4 km/h`;
- metriques presentes: toutes les metriques attendues sauf `vco2_l_min`
  natif;
- EC utilise donc le fallback explicite `derived_vo2_x_rer`;
- warning observe:
  `ventilatory_vo2_consistency`, diff moyenne `0.1013`.

### Limites Tkinter actuelles

La V1 CustomTkinter est correcte comme preuve de flux local, mais elle reste le
mauvais outil pour l'UX cible:

- Plotly/drag/zoom/fullscreen sont deja mieux geres dans React;
- le drag fin de bornes de fenetre est plus fragile en matplotlib;
- la grille de graphes et le panneau marqueurs deviennent vite denses;
- le rendu visuel est loin de la branche dashboard validee;
- ajouter plus d'interactions a Tkinter augmenterait une dette qui sera jetee.

Decision: ne pas continuer a renforcer la V1 graphique Tkinter. Garder
CustomTkinter comme shell session/profil/matching, et deplacer seulement la
lecture MetaSoft interactive dans React local.

### Assets React/dashboard disponibles

Source principale:
`/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft`

Fichiers a reprendre/adapater:

- `graphConfig.ts`
  - config des graphes et couleurs marqueurs.
- `chartUtils.ts`
  - shapes phases, vitesses, marqueurs, annotations.
- `markerUtils.ts`
  - horloge, marqueurs initiaux, moyennes de fenetre cote dashboard.
- `MetaSoftChart.tsx`
  - Plotly;
  - zoom drag;
  - double-clic reset;
  - fullscreen;
  - toggles series;
  - overlays phases/vitesses/marqueurs;
  - drag centre/bornes;
  - clic droit suppression.
- `MarkerPanel.tsx`
  - panneau marqueurs et editions fenetres.
- `CursorRail.tsx`
  - lecture point survole.
- `AnalysisExportSection.tsx`
  - EC, warnings, resume marqueurs, export.
- `downloadUtils.ts`
  - utile pour audit CSV local si conserve.

Fichiers a ne pas reprendre tels quels:

- `MetaSoftUploadToolbar.tsx`: l'app locale part d'un match profil/XML, pas
  d'un upload libre comme le dashboard.
- `metasoftService.ts`: endpoints dashboard auth a remplacer par endpoints
  locaux `127.0.0.1`, sans `/auth/api`, sans BDD.
- `CoachMetaSoftTestingPage.tsx`: structure utile, mais entree upload/export
  stateless a remplacer par contexte session.

## 2. Architecture cible minimale

### Principe Ponytail

La migration React a un cout reel. Le minimum qui tient:

- pas de FastAPI/Flask si `http.server.ThreadingHTTPServer` suffit;
- pas de pywebview au lot 1;
- pas de design system parallele;
- pas de shadcn complet dans l'app locale;
- pas d'upload XML React si le match local existe deja;
- pas de recalcul officiel en React.

### Processus runtime

```text
python main.py
  TCPDataProcessorSession (CustomTkinter)
    Sessions / Profils / XML / Matching
    bouton Analyser(match)
      LocalReactServer.ensure_started(session_manager)
      open http://127.0.0.1:<port>/metasoft?match_id=<id>

LocalReactServer
  sert frontend build local
  expose API JSON locale
  tient une reference au SessionManager actif
  refuse toute route BDD/ecriture externe

React local
  lit /api/matches/<match_id>/analysis
  affiche graphes Plotly
  gere localement preview clic/drag/fenetres/zoom
  conserve des selections marqueurs non officielles
  envoie les selections a Python seulement sur action engageante
  recoit les valeurs officielles confirmees
  demande report profil/export
```

### Preview frontend vs officialisation backend

Contrat d'interaction souhaite:

- React gere la fluidite locale: clic, popup, drag centre/bornes, edition
  debut/fin, zoom, fullscreen, lissage, overlays.
- React peut afficher une preview depuis les points deja charges pour aider le
  coach, mais cette preview est marquee non officielle.
- React conserve seulement des selections:
  `name`, `mode`, `t_seconds`, `window_start_seconds`, `window_end_seconds`.
- Aucun aller-retour Python a chaque clic, drag ou mouse up.
- Python officialise en batch seulement au clic `Sauvegarder`,
  `Reporter au profil` ou `Exporter`.
- Les valeurs sauvegardees, reportees au profil, exportees dans le JSON ou le
  sidecar viennent uniquement de `build_metasoft_marker` cote Python sur les
  points bruts.
- Apres officialisation, React remplace la preview par les valeurs confirmees
  et affiche les warnings backend.

Nom de modele cote React:

```ts
type MarkerSelectionDraft = {
  name: "SV1" | "SV2" | "VO2_max" | "VMA";
  mode: "point" | "range";
  t_seconds: number | null;
  window_start_seconds: number | null;
  window_end_seconds: number | null;
};
```

Le draft est une intention d'UI, pas une mesure officielle.

### Serveur local Python

Recommendation initiale:
`src/local_api/metasoft_server.py` avec stdlib:

- `http.server.ThreadingHTTPServer`;
- `BaseHTTPRequestHandler`;
- `json`;
- `urllib.parse`;
- `mimetypes`;
- `threading`;
- `webbrowser`;
- port ephemeral sur `127.0.0.1`;
- token local aleatoire par process pour eviter qu'un autre site localhost
  appelle l'API sans contexte.

Pourquoi pas FastAPI au premier lot:

- dependance runtime supplementaire;
- packaging PyInstaller plus large;
- aucun besoin d'OpenAPI public;
- endpoints peu nombreux;
- pas d'upload multipart si on part du match local existant.

Upgrade acceptable:
FastAPI/uvicorn uniquement si les handlers stdlib deviennent illisibles ou si
le besoin d'upload/debug API augmente. Ce serait un GO separe.

### UI React build/dev

Nouveau dossier propose:

```text
local_ui/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    App.tsx
    metasoft/
      api.ts
      types.ts
      graphConfig.ts
      chartUtils.ts
      markerTimeUtils.ts
      MetaSoftLocalPage.tsx
      MetaSoftChart.tsx
      MarkerPanel.tsx
      ExportPanel.tsx
      CursorRail.tsx
    styles.css
```

Dependances frontend minimales:

- `react`;
- `react-dom`;
- `vite`;
- `typescript`;
- `@vitejs/plugin-react-swc`;
- `react-plotly.js`;
- `plotly.js-dist-min` ou equivalent compatible;
- `lucide-react` optionnel pour icones.

Dependances a eviter au lot 1:

- Radix/shadcn complet;
- axios, car `fetch` suffit;
- react-query, car une page locale a peu de cache distant;
- Tailwind si les composants adaptes peuvent etre stylises en CSS local;
- Vitest/Playwright si le build TypeScript + smoke local couvre le lot. Ajouter
  seulement si de la logique React pure devient critique.

### Lancement depuis Python

Flux cible:

1. `XML Matching` garde le bouton `Analyser`.
2. `_analyze_match(match_info)` ne lance plus la fenetre graphes Tkinter.
3. `_analyze_match` demarre ou reutilise le serveur local.
4. Le serveur encode `match_id` depuis `profile_name + xml_filename`.
5. Python ouvre l'URL via `webbrowser.open`.
6. Si `webbrowser.open` echoue, afficher l'URL copiable.
7. Webview devient optionnel apres validation packaging.

### Stockage/export local

Source unique:
`SessionManager`.

Ecritures locales autorisees:

- `profiles/*.json` via `update_profile`;
- `output/*.json` via `save_output`;
- `output/*.metasoft_audit.json` via `save_output`;
- eventuel cache `local_ui/dist` uniquement au build, pas au runtime session.

Ecritures interdites:

- Mongo;
- BDD prod;
- dossier dashboard;
- fichier XML source hors copie session;
- export depuis React directement dans `Downloads` comme source officielle.

## 3. Contrats API exacts

Toutes les routes sont locales:
`http://127.0.0.1:<port>`.

Toutes les routes API exigent le header:

```http
X-Enduraw-Local-Token: <token_process>
```

Le token est injecte dans l'URL de depart ou dans un petit bootstrap JSON
statique servi par Python. Aucun secret long terme.

### Erreur standard

```json
{
  "ok": false,
  "error": {
    "code": "profile_not_found",
    "message": "Profil local introuvable.",
    "blocking": true,
    "details": {}
  },
  "warnings": []
}
```

Codes initiaux:

- `invalid_token`
- `session_not_loaded`
- `match_not_found`
- `profile_not_found`
- `xml_not_found`
- `xml_parse_failed`
- `invalid_marker_selection`
- `marker_blocked`
- `profile_conflict`
- `export_validation_failed`
- `internal_error`

### `GET /api/health`

Reponse:

```json
{
  "ok": true,
  "app": "enduraw_testing_tool",
  "mode": "local",
  "api_version": 1
}
```

### `GET /api/session`

Reponse:

```json
{
  "ok": true,
  "session": {
    "name": "2026-07-08_contas",
    "date": "2026-07-08",
    "location": "contas"
  }
}
```

### `GET /api/matches`

Reponse:

```json
{
  "ok": true,
  "matches": [
    {
      "match_id": "sha256-12chars",
      "profile_name": "forms_Mo_Arthur.json",
      "xml_filename": "TCP__VAN DER VEEN_Noor_2026.06.10_12.38.06_.xml",
      "exported": false
    }
  ]
}
```

### `GET /api/matches/{match_id}/analysis`

Responsabilite:

- lire profil local;
- lire XML local de session;
- parser XML via `TCPXmlParser`;
- recalculer analyse avec masse profil seulement si masse XML absente;
- retourner analyse, profil utile, warnings;
- ne rien ecrire.

Reponse:

```json
{
  "ok": true,
  "match": {
    "match_id": "sha256-12chars",
    "profile_name": "forms_Mo_Arthur.json",
    "xml_filename": "TCP__VAN DER VEEN_Noor_2026.06.10_12.38.06_.xml"
  },
  "profile": {
    "identity": {
      "first_name": "Arthur",
      "last_name": "Mo"
    },
    "stress_test_results": {
      "thresholds": {
        "sv1": {},
        "sv2": {}
      },
      "measured_vo2max": null,
      "max_hr": null,
      "vma": null
    }
  },
  "analysis": {
    "file": {},
    "athlete": {},
    "test": {},
    "metrics": {},
    "points": [],
    "phases": [],
    "warmup_stages": [],
    "computed": {},
    "warnings": []
  },
  "warnings": [
    {
      "code": "identity_mismatch",
      "message": "Identite XML differente du profil local; export non bloque.",
      "blocking": false
    }
  ],
  "source_of_truth": {
    "metrics": "python.metasoft_analysis",
    "markers": "python.metasoft_markers",
    "export": "python.data_transformer + python.metasoft_audit_export",
    "smoothing": "react_visual_only"
  }
}
```

Payload React interdit:

- pas de valeurs marqueurs calculees par React comme officielles;
- pas de valeurs lissees;
- pas de donnees exportees directement depuis Plotly.

### `POST /api/matches/{match_id}/markers/officialize`

Responsabilite:

- recevoir une liste de selections frontend;
- appeler `build_metasoft_marker` pour chaque selection;
- retourner les marqueurs officiels confirmes;
- ne rien ecrire.

Usage:

- bouton `Sauvegarder` si on veut figer les valeurs confirmees dans l'UI;
- appele implicitement par `profile/report-preview`, `profile/report` et
  `export`;
- jamais appele a chaque clic/drag.

Requete:

```json
{
  "marker_selections": [
    {
      "name": "SV1",
      "mode": "point",
      "t_seconds": 742.25,
      "window_start_seconds": null,
      "window_end_seconds": null
    },
    {
      "name": "SV2",
      "mode": "range",
      "t_seconds": 1180.0,
      "window_start_seconds": 1060.0,
      "window_end_seconds": 1300.0
    }
  ]
}
```

Reponse:

```json
{
  "ok": true,
  "markers": {
    "SV2": {
      "name": "SV2",
      "mode": "range",
      "status": "ok",
      "selection_time_seconds": 1180.0,
      "window_start_seconds": 1060.0,
      "window_end_seconds": 1300.0,
      "point_count": 72,
      "values": {
        "fc_bpm": 170.0,
        "vo2_l_min": 3.2,
        "vo2_ml_kg_min": 47.1,
        "speed_kmh": 15.0,
        "vma": null
      },
      "warnings": []
    }
  },
  "source": "python.build_metasoft_marker",
  "warnings": []
}
```

### `POST /api/matches/{match_id}/profile/report-preview`

Responsabilite:

- officialiser les selections puis convertir les marqueurs confirmes en patch
  profil;
- detecter conflits;
- ne rien ecrire.

Requete:

```json
{
  "marker_selections": []
}
```

Le backend officialise d'abord les selections via `build_metasoft_marker`, puis
construit le patch profil depuis les marqueurs confirmes. Les valeurs preview
React sont ignorees si elles sont envoyees par erreur.

Reponse sans conflit:

```json
{
  "ok": true,
  "status": "ready",
  "patch": {
    "stress_test_results": {}
  },
  "conflicts": [],
  "warnings": []
}
```

Reponse avec conflits:

```json
{
  "ok": true,
  "status": "conflict",
  "patch": {},
  "conflicts": [
    {
      "path": "stress_test_results.thresholds.sv1.hr_bpm",
      "current": 148,
      "incoming": 151.3
    }
  ],
  "warnings": []
}
```

### `POST /api/matches/{match_id}/profile/report`

Responsabilite:

- appliquer le patch seulement apres confirmation explicite;
- ecrire via `SessionManager.update_profile`;
- retourner le nouveau nom de profil si renommage.

Requete:

```json
{
  "marker_selections": [],
  "conflict_policy": "keep_existing|overwrite"
}
```

Reponse:

```json
{
  "ok": true,
  "profile_name": "forms_Mo_Arthur.json",
  "updated_paths": [
    "stress_test_results.thresholds.sv1.hr_bpm",
    "stress_test_results.vma"
  ],
  "confirmed_markers": {},
  "warnings": []
}
```

### `POST /api/matches/{match_id}/export`

Responsabilite:

- reparser ou reutiliser l'analyse du match;
- officialiser/valider les selections recues si necessaire;
- transformer via `DataTransformer`;
- sauver JSON principal via `SessionManager.save_output`;
- sauver sidecar via `build_metasoft_audit_export`;
- marquer le match exporte si succes;
- ne pas ecrire ailleurs.

Requete:

```json
{
  "marker_selections": [],
  "include_audit_points": false
}
```

Le backend officialise les selections dans la meme transaction logique que
l'export. Le JSON et le sidecar utilisent les marqueurs confirmes, jamais les
valeurs de preview React.

Reponse:

```json
{
  "ok": true,
  "json": {
    "filename": "Mo_Arthur_2026-07-08.json",
    "path": "sessions/2026-07-08_contas/output/Mo_Arthur_2026-07-08.json"
  },
  "audit": {
    "filename": "Mo_Arthur_2026-07-08.metasoft_audit.json",
    "path": "sessions/2026-07-08_contas/output/Mo_Arthur_2026-07-08.metasoft_audit.json"
  },
  "confirmed_markers": {},
  "warnings": [],
  "blocking_errors": []
}
```

Si export invalide:

```json
{
  "ok": false,
  "error": {
    "code": "export_validation_failed",
    "message": "Export JSON incomplet.",
    "blocking": true
  },
  "blocking_errors": [
    {
      "field": "SV1",
      "message": "Champ obligatoire manquant: SV1."
    }
  ],
  "warnings": []
}
```

## 4. Mapping dashboard -> React local

### A reprendre presque tel quel

`graphConfig.ts`

- reprendre les 9 graphes comme config declarative;
- adapter le 8e graphe: le dashboard courant expose `speed`, mais l'app locale
  doit garder `running_economy` comme graphe cible si c'est le besoin produit;
- conserver couleurs marqueurs.

`chartUtils.ts`

- reprendre overlays phases;
- reprendre speed bands et labels vitesse;
- garder fallback depuis `analysis.points`;
- adapter `Retablissement` sans accent et `Rétablissement` avec accent.

`MetaSoftChart.tsx`

- reprendre Plotly, zoom, double-clic reset, fullscreen, toggles series;
- garder `buildMarker` ou equivalent uniquement comme preview frontend;
- ne pas appeler Python pendant clic/drag/mouse up;
- stocker les `MarkerSelectionDraft` localement;
- afficher les valeurs preview comme non officielles jusqu'a sauvegarde,
  report ou export.

`MarkerPanel.tsx`

- reprendre table et edition debut/fin;
- recalculer la preview localement pour rester fluide;
- appeler `/markers/officialize` seulement via bouton `Sauvegarder` ou
  implicitement via report/export;
- afficher cote a cote si utile: preview frontend et valeurs confirmees Python;
- ajouter source officielle et warnings backend par marqueur confirme.

`CursorRail.tsx`

- reprendre pour valeurs au survol;
- ne pas afficher de valeur lisse comme officielle.

### A adapter fortement

`CoachMetaSoftTestingPage.tsx`

- supprimer upload/drag-drop;
- charger depuis `match_id`;
- layout cible: lecture graphes + panneau marqueurs + export local;
- phase filter et smoothing conserves.

`AnalysisExportSection.tsx`

- garder EC/table/warnings;
- supprimer formulaire manuel duplicatif si les infos existent dans le profil;
- afficher les champs manquants du profil et proposer "ouvrir profil" cote
  shell Tkinter plus tard si necessaire;
- bouton export appelle `/api/matches/{match_id}/export`.

`metasoftService.ts`

- remplacer axios dashboard par `fetch`;
- base URL relative;
- header token local.

`types/metasoft.ts`

- aligner sur le contrat Python actuel:
  `values.fc_bpm`, pas `values.fc`;
- accepter `status`, `mode`, `warnings`, `source_point_t_seconds` sur
  marqueurs officiels;
- garder `MetaSoftMetricKey` identique.

### A garder cote Python uniquement

- parsing XML;
- detection phases officielle;
- detection paliers EC officielle;
- EC officielle;
- marqueurs officiels;
- mapping profil;
- conflits profil;
- JSON Valentin;
- sidecar audit;
- validation export bloquante;
- lecture/ecriture session.

### A garder cote React uniquement

- layout;
- Plotly;
- lissage visuel;
- zoom/pan/fullscreen;
- preview de drag;
- preview non officielle des valeurs marqueurs depuis les points charges;
- position popup;
- toggles de series visibles;
- filtres d'affichage;
- formatage local non officiel.

## 5. UX cible detaillee

### Entree utilisateur

Dans l'app Python locale:

- l'utilisateur reste dans `XML Matching`;
- chaque match affiche `Analyser`, `Exporter`, `X`;
- `Analyser` ouvre la lecture React locale pour ce match;
- `Exporter tout` reste dans le shell Python et ne lance pas React.

### Page React locale

Header:

- nom XML;
- nom profil;
- date test;
- nombre de points;
- warnings data;
- alerte identite non bloquante:
  `XML: VAN DER VEEN Noor / Profil: Mo Arthur`.

Toolbar:

- lissage: `0`, `15`, `30`, `60`, `120`, `240 s`;
- filtre phase: `Tout`, puis phases du XML;
- reset zoom global si possible;
- bouton export JSON + audit;
- bouton report profil;
- statut "Python source de verite" discret dans panneau details, pas en
  grand texte pedagogique.

Graphes:

1. `FC + V'O2`
2. `V'O2/kg + vitesse`
3. `V'E + BF`
4. `RER`
5. `V'E/V'O2 + V'E/V'CO2`
6. `PetO2 + PetCO2`
7. `DE / DECHO / DEFAT / DEPRO`
8. `Economie de course`
9. `Synthese seuils`

Comportements pour chaque graphe:

- Plotly zoom drag;
- double-clic reset;
- fullscreen;
- series toggle;
- series manquantes affichees;
- overlays phases en bas;
- bandes vitesses en background;
- labels vitesse pour segments assez longs;
- marqueurs communs visibles;
- hover/cursor valeurs au point.

Lissage:

- visuel uniquement;
- jamais applique a `speed_kmh`;
- jamais renvoye a Python;
- jamais exporte;
- jamais utilise pour marker/profile/export.

Marqueurs:

- `SV1`;
- `SV2`;
- `VO2max` (`VO2_max` code);
- `VMA`;
- clic exact sur axe temps;
- mode point;
- mode fenetre;
- fenetre par defaut: hypothese `4:00` pour compatibilite V1 locale, a
  confirmer si la branche dashboard doit imposer `2:00`;
- edition manuelle debut/fin;
- drag centre;
- drag bornes;
- clic droit suppression;
- preview locale immediate;
- officialisation Python seulement au clic `Sauvegarder`, `Reporter au profil`
  ou `Exporter`.

Table marqueurs:

- marqueur;
- mode;
- temps selection;
- debut;
- fin;
- points;
- FC `bpm`;
- VO2 `ml/kg/min`;
- VO2 `L/min`;
- vitesse `km/h`;
- statut: `preview` ou `confirme_python`;
- source officielle apres sauvegarde: `point_brut` ou
  `moyenne_fenetre_brute`;
- warnings backend apres officialisation.

Report profil:

- bouton `Reporter au profil`;
- officialise d'abord les selections via Python;
- preview conflits basee sur les valeurs confirmees Python;
- ecrasement seulement apres confirmation;
- refus conserve les marqueurs dans la page sans modifier profil;
- ecriture via `SessionManager.update_profile`.

Export:

- bouton `Exporter JSON + audit`;
- officialise d'abord les selections via Python;
- JSON strict conserve;
- sidecar audit local obligatoire;
- chemins de sortie affiches apres succes;
- blocking errors visibles si profil/marqueurs incomplets.

## 6. Plan sequentiel par lots

Chaque lot suit:

1. plan court avant implementation du lot;
2. implementation;
3. audit thermo-nuclear du diff;
4. corrections;
5. checks cibles;
6. pas de stage/commit/push sans GO.

### Lot 0 - Gel des contrats

Write scope:

- `docs/metasoft_react_local_ui_migration_plan.md`;
- eventuellement un doc court de contrats si GO separe.

Dependances:

- aucune.

Tests/checks:

- lecture `git status --short --branch`;
- pas de code.

Audit attendu:

- verifier que le plan ne deplace pas la logique officielle en React;
- verifier que le serveur local ne cree pas de BDD/write externe.

### Lot 1 - API locale Python minimale

Write scope:

- `src/local_api/metasoft_server.py`;
- petits ajouts dans `src/main_session.py` pour lancer serveur;
- tests Python proches.

Dependances:

- stdlib seulement si possible.

Implementation:

- registry match_id -> profil/XML depuis `SessionManager.matches`;
- static serving prepare mais peut retourner une page placeholder si frontend
  pas encore present;
- routes `health`, `session`, `matches`, `analysis`,
  `markers/officialize`, `profile/report-preview`, `profile/report`,
  `export`;
- token local process;
- port ephemeral `127.0.0.1`;
- aucune route Mongo.

Tests:

- `PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_local_api.py`;
- tests erreurs: pas de session, match inconnu, token invalide;
- test marker officialize batch sur selections synthetiques;
- test export ecrit dans session temporaire.

Audit:

- pas de handler geant au-dessus de 800-1000 lignes;
- si le routing stdlib devient illisible, extraire un dispatcher simple;
- pas de duplication de `DataTransformer` ou `SessionManager`.

### Lot 2 - Frontend Vite React local

Write scope:

- `local_ui/`;
- README court de lancement dev si necessaire.

Dependances:

- Node/Vite en dev/build;
- pas de runtime Node dans l'executable final.

Implementation:

- page `MetaSoftLocalPage`;
- `api.ts` en `fetch`;
- types alignes Python;
- affichage analysis depuis `GET /analysis`;
- graphes Plotly avec config reprise/adaptee;
- state local `MarkerSelectionDraft`;
- preview marqueurs locale sans appel API pendant clic/drag;
- lissage visuel;
- overlays phases/vitesses/marqueurs;
- fullscreen.

Tests:

- `cd local_ui && npm install` si lock absent;
- `npm run build`;
- `npm run typecheck` si script ajoute;
- smoke navigateur via serveur local.

Audit:

- pas de design system parallele;
- pas de copie shadcn massive;
- pas de composant page monolithe si > 800-1000 lignes;
- `MetaSoftChart` peut rester dense mais les fonctions temps/drag doivent
  rester isolees.

### Lot 3 - Marqueurs officiels, report profil, export

Write scope:

- `local_ui/src/metasoft/*`;
- `src/local_api/metasoft_server.py`;
- tests Python/API;
- checks frontend.

Dependances:

- Lot 1 et Lot 2.

Implementation:

- React envoie les selections a Python seulement sur `Sauvegarder`, report ou
  export;
- Python retourne les marqueurs officiels confirmes;
- UI garde la preview fluide, puis remplace/complete par les valeurs
  confirmees;
- report preview + confirmation conflits;
- export JSON + audit sidecar;
- messages erreurs/warnings.

Tests:

- unit Python markers/report/export;
- test API: selection point/range, conflit profil, export;
- `npm run build`;
- smoke manuel sur XML reel en lecture, sorties dans session locale seulement.

Audit:

- verifier qu'aucun marker officiel n'est calcule cote React;
- verifier qu'aucune valeur lissee n'entre dans payload export/report;
- verifier qu'aucun aller-retour API n'est declenche par drag/clic simple;
- verifier que les conflits profil ne sont pas ecrases silencieusement.

### Lot 4 - Packaging/lancement

Write scope:

- `README.md` ou doc packaging;
- script build existant si present ou spec PyInstaller si deja utilise;
- ajout PyInstaller data pour `local_ui/dist`.
- launcher/icône desktop, avec le logo fourni par Arthur:
  `/Users/arthurmo/Downloads/LOGO_ENDURAW_HORIZONTAL_WHITE.png`.

Dependances:

- Lots 1 a 3 stables.

Implementation:

- `npm run build` produit `local_ui/dist`;
- PyInstaller inclut `local_ui/dist`;
- Python resout le chemin dist en mode source et mode frozen;
- `webbrowser.open` par defaut;
- URL fallback affichee si ouverture echoue.
- l'icône/launcher cliquable de l'ordinateur utilise une ressource Enduraw
  propre, derivee du logo fourni, sans dependre du fichier dans `Downloads` au
  runtime final.

Tests:

- Mac: lancement source `python main.py`;
- Mac: build PyInstaller si possible;
- Windows: a faire sur machine Windows ou CI Windows si disponible;
- verifier que Node n'est pas requis au runtime.

Audit:

- pywebview reste hors lot sauf GO;
- pas de chemin absolu local dans le build;
- pas de fichier XML/output package.
- pas de dependance runtime au fichier logo source dans `Downloads`.

### Lot 5 - Perf, data precision, GO/NO-GO

Write scope:

- tests/perf scripts cibles si GO;
- doc resultats.

Dependances:

- lots precedents.

Implementation/checks:

- XML reel `5.6 MB`;
- XML cible synthetique ou reel `20 MB`;
- temps parse Python;
- temps reponse `/analysis`;
- taille JSON analysis;
- temps rendu React;
- memoire approximative;
- export batch 30-40 matches sans ouvrir React.

Audit:

- si `/analysis` devient trop lourd, ajouter une decimation visuelle separee
  uniquement pour React, tout en gardant markers officiels sur points bruts
  cote Python;
- ne pas decimer le sidecar ou les exports officiels sans champ audit clair.

## 7. Strategie packaging/lancement

### Dev

Mode dev propose:

```text
Terminal 1: python main.py
Terminal 2: cd local_ui && npm run dev
```

Le serveur Python peut accepter une variable:

```text
ENDURAW_LOCAL_UI_DEV_URL=http://127.0.0.1:5173
```

En dev, `Analyser` ouvre Vite. En prod, `Analyser` ouvre le build statique servi
par Python.

### Runtime source

Sans build executable:

- `python main.py`;
- serveur local Python sert `local_ui/dist` si present;
- sinon message clair: lancer `npm run build` ou utiliser Vite dev.

### Executable Mac/Windows

PyInstaller doit inclure:

- `src/`;
- `local_ui/dist/`;
- icone existante;
- fichiers config necessaires.

Node/Vite ne doivent pas etre requis au runtime.

### Webview

Decision initiale:
navigateur local par defaut.

Raison:

- `webbrowser` est stdlib;
- packaging plus simple;
- moins de risques Mac/Windows;
- l'UX Plotly fonctionne dans navigateur moderne.

GO webview seulement si:

- les utilisateurs refusent l'ouverture navigateur;
- le build PyInstaller navigateur est valide;
- le cout `pywebview` Mac/Windows est mesure.

Fallback obligatoire si webview ajoute:

- ouvrir navigateur local si webview indisponible;
- ne pas bloquer l'analyse MetaSoft sur un probleme webview.

## 8. Tests/checks

### Python unit/integration

Commandes cibles:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_local_core.py
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_audit_export.py
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_main_session_export.py
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_local_api.py
```

Checks obligatoires:

- parser respecte `ss:Index`;
- analyse EC garde source/unite/fallback;
- marker point utilise point brut le plus proche;
- marker range moyenne points bruts;
- marker ignore `None`, ne remplace jamais par `0`;
- report profil detecte conflits;
- export JSON strict ne contient pas `metasoft_analysis` top-level;
- sidecar contient sources, unites, warnings, marqueurs;
- API refuse token invalide;
- API n'appelle pas Mongo.

### Frontend

Commandes cibles:

```bash
cd local_ui
npm run typecheck
npm run build
```

Si `lint` est configure sans cout excessif:

```bash
npm run lint
```

Tests purs a envisager seulement si la logique grandit:

- `secondsToClock`;
- `clockToSeconds`;
- bornage drag start/end;
- `smoothSeries` visuel.
- conversion `MarkerSelectionDraft` sans valeur officielle.

Ponytail: ne pas ajouter Vitest juste pour tester un wrapper trivial. Ajouter
un runner JS seulement si ces helpers deviennent critiques ou regressent.

### Smoke end-to-end local

Cas minimal:

1. lancer `python main.py`;
2. charger une session avec match profil/XML;
3. clic `Analyser`;
4. verifier ouverture React;
5. verifier 9 graphes;
6. zoom drag puis double-clic reset;
7. fullscreen;
8. lissage `0` puis `60 s`;
9. poser `SV1` point;
10. poser `SV2` range;
11. drag fenetre;
12. poser `VO2max`;
13. poser `VMA`;
14. verifier qu'aucun appel officialisation n'est necessaire pendant le drag;
15. cliquer `Sauvegarder` ou `Reporter au profil` et verifier les valeurs
    confirmees Python;
16. report profil avec confirmation conflit si champ deja rempli;
17. export JSON + audit;
18. verifier fichiers dans `sessions/<session>/output`.

### Perf XML 20 MB

Objectifs a mesurer, pas supposer:

- parse XML Python;
- temps `/analysis`;
- taille payload JSON;
- temps premier rendu React;
- zoom/drag fluide;
- absence d'aller-retour API pendant clic/drag;
- export JSON + audit;
- memoire processus Python et navigateur si observable.

Seuils GO proposes:

- XML `20 MB` parse sans crash;
- UI interactive apres chargement initial;
- drag marker sans latence bloquante;
- export local termine;
- aucun output lisse/officiel faux.

Si payload trop lourd:

- garder points bruts cote Python pour marqueurs;
- envoyer a React une serie visuelle decimee separee;
- `/markers/officialize` continue d'utiliser les points bruts au moment
  sauvegarde/report/export;
- sidecar documente la decimation si des points audit sont inclus.

## 9. Risques, hypotheses, GO/NO-GO

### Risques

- Plotly augmente fortement la taille du bundle.
- `react-plotly.js` + Plotly peut compliquer le build PyInstaller si assets mal
  resolus.
- Le serveur stdlib peut devenir illisible si on ajoute trop de routes.
- React peut tenter de recalculer les marqueurs pour aller plus vite.
- L'UI peut redevenir lente si elle officialise a chaque drag au lieu de garder
  une preview locale.
- Les types dashboard ne correspondent pas exactement au Python local
  (`fc` vs `fc_bpm`).
- La branche dashboard contient une config 9e graphe `speed`, alors que le
  besoin local demande `Economie de course`; arbitrage produit a figer.
- Webview peut couter plus cher que sa valeur au premier lot.
- XML `20 MB` peut rendre le payload `/analysis` trop gros si tous les `raw`
  sont envoyes.

### Hypotheses explicites

- Le shell CustomTkinter reste en place pour sessions/profils/matching.
- React ne gere pas la creation de session/profil au premier lot.
- Le match profil/XML existe avant ouverture React.
- L'app locale peut ouvrir un navigateur par defaut.
- Python peut servir le build React depuis `local_ui/dist`.
- La V1 Tkinter MetaSoft devient reference fonctionnelle temporaire, pas cible
  UX.
- React garde les selections marqueurs en preview locale.
- Les marqueurs officiels sont recalcules cote Python seulement sur
  sauvegarde/report/export.
- Le lissage React est acceptable uniquement comme transformation visuelle.

### Criteres GO

- API locale sans BDD, sans dependance serveur lourde.
- 9 graphes React visibles et utilisables.
- Zoom drag, double-clic reset, fullscreen fonctionnels.
- Overlays phases/vitesses/marqueurs presents.
- Lissage visuel prouve non exporte.
- Markers officiels retournes par Python.
- Report profil ecrit localement avec conflits explicites.
- Export JSON strict + sidecar audit ecrit localement.
- Build frontend passe.
- Tests Python cibles passent.
- Smoke XML reel passe.
- Packaging source valide; executable planifie ou valide selon lot.

### Criteres NO-GO

- React calcule une metrique officielle ou un marqueur officiel.
- Une valeur lissee arrive dans profil/export/sidecar officiel.
- Une route ecrit en BDD ou appelle une ecriture prod.
- `dashboard/backend/activities/router.py` doit etre modifie pour faire marcher
  le local.
- Le packaging exige Node au runtime final.
- Le serveur local expose une API sans token/process guard.
- Le flux local contourne `SessionManager` pour ecrire profils/output.
- Le diff ajoute un framework serveur sans justification mesuree.

## Conclusion architecture

La migration React locale est justifiee pour l'UX graphique, pas pour la logique
metier. Le plus petit design robuste est donc:

- Python garde tout ce qui decide;
- React affiche et exprime des intentions;
- serveur local stdlib d'abord;
- navigateur d'abord;
- webview et framework serveur seulement apres preuve de besoin.
