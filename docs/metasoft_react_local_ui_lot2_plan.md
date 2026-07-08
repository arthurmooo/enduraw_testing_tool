# Lot 2 - UI React locale MetaSoft

Date: 2026-07-08

## Objectif

Construire une UI React locale testable, ouverte depuis l'app Python, pour
lire les 9 graphes MetaSoft, ajuster le lissage, zoomer, poser/drag des
marqueurs en preview, puis officialiser/report/export via l'API Python locale.

Cette UI remplace l'interface Tkinter MetaSoft visuellement, mais ne remplace
pas la source de verite Python.

## Non-negociables

- aucun push BDD;
- aucun appel Mongo depuis React;
- aucun calcul officiel de marqueur dans React;
- aucun export JSON officiel depuis React;
- aucun marqueur lisse/exporte: le lissage est visuel seulement;
- aucun aller-retour API pendant hover, click simple, drag marqueur ou zoom;
- `backend/activities/router.py` du dashboard reste intouchable;
- `run.sh` est hors Lot 2 sauf GO explicite separe.

## Sources a reutiliser

Repo destination:

- `/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool`

Source React a lire/copier-adapter:

- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/pages/coach/CoachMetaSoftTestingPage.tsx`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft/MetaSoftChart.tsx`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft/chartUtils.ts`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft/graphConfig.ts`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft/markerUtils.ts`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft/CursorRail.tsx`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft/MetaSoftUploadToolbar.tsx`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/components/coach-metasoft/AnalysisExportSection.tsx`
- `/Users/arthurmo/Developer/Enduraw/code/dashboard/frontend/src/types/metasoft.ts`

Important: copier l'UX et les helpers visuels, pas le contrat backend dashboard.
Le service `metasoftService.ts` du dashboard doit etre remplace par un client
API local.

Source locale a respecter pour la liste officielle des graphes:

- `/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool/src/ui/metasoft_graphs.py`

Les 9 graphes Lot 2 sont verrouilles sur ces IDs, dans cet ordre:

1. `fc_vo2`
2. `vo2kg_speed`
3. `ve_bf`
4. `rer`
5. `ve_ratios`
6. `pet`
7. `de`
8. `running_economy`
9. `thresholds`

Ne pas remplacer `running_economy` par le graphe `speed` du dashboard: l'EC est
un noyau MVP explicite.

## Write scope Lot 2

- `local_ui/package.json`
- `local_ui/package-lock.json` si genere par `npm install`
- `local_ui/index.html`
- `local_ui/tsconfig*.json`
- `local_ui/vite.config.ts`
- `local_ui/src/**`
- ajustement minimal de `src/local_api/metasoft_server.py` seulement si requis
  pour servir correctement les assets Vite buildes;
- tests Python API seulement si un contrat necessaire manque.

## Architecture

### Runtime

1. L'utilisateur clique `Analyser` dans l'app Python.
2. Python demarre/reutilise `LocalMetaSoftServer`.
3. Python ouvre:
   `http://127.0.0.1:<port>/metasoft?match_id=<id>&token=<token>`
4. React lit `match_id` et `token` depuis `window.location`.
5. React appelle:
   - `GET /api/matches/:match_id/analysis`
   - `POST /api/matches/:match_id/markers/officialize`
   - `POST /api/matches/:match_id/profile/report-preview`
   - `POST /api/matches/:match_id/profile/report`
   - `POST /api/matches/:match_id/export`
6. Chaque appel `/api/*` envoie `X-Enduraw-Local-Token`.

### Source de verite

React garde deux etats separes:

- `draftMarkers`: preview visuelle, instantanee, modifiable par click/drag;
- `confirmedMarkers`: retour Python apres officialisation.
- `dirtyMarkers`: set des marqueurs modifies depuis la derniere officialisation
  Python.

Les graphes affichent `draftMarkers` pour rester fluides. Les tableaux
d'export/report affichent `confirmedMarkers` uniquement si le marqueur n'est pas
dirty. Toute modification draft apres officialisation invalide le confirmed du
marqueur concerne ou marque l'etat `needsSave`.

Report/export doivent toujours serialiser les drafts courants, appeler Python,
puis remplacer `confirmedMarkers` par le retour Python. Aucune ancienne valeur
confirmee ne doit rester visible comme officielle apres un drag/click non
sauvegarde.

Le payload envoye a Python contient seulement:

```json
{
  "marker_selections": [
    {
      "name": "SV1",
      "mode": "range",
      "t_seconds": 1599,
      "window_start_seconds": 1479,
      "window_end_seconds": 1719
    }
  ]
}
```

React n'envoie pas les valeurs calculees, pas les courbes lissees, pas les
moyennes preview.

Créer obligatoirement `serializeMarkerSelections(draftMarkers)`. Cette fonction
ne retourne que:

- `name`
- `mode`
- `t_seconds`
- `window_start_seconds`
- `window_end_seconds`

Interdit dans `marker_selections`: `values`, `preview`, `smoothed_values`,
`point_count`, `phase`.

### API client local

Créer `local_ui/src/lib/localApi.ts`:

- `getBootstrap()` lit `match_id` et `token`;
- `apiGet(path)` et `apiPost(path, body)` injectent le header token;
- erreurs API normalisees avec `error.code`, `message`, `details`;
- `ApiError` doit lire `payload.error`, pas des champs top-level;
- `/profile/report-preview` retourne `status`, `conflicts`, `patch`,
  `confirmed_markers`;
- `/profile/report` peut retourner HTTP `409` avec
  `error.details.conflicts`, puis HTTP `200` avec `confirmed_markers` apres
  `conflict_policy: "overwrite"`;
- pas d'axios: `fetch` natif suffit.

### UI

Premier ecran:

- header Enduraw sobre;
- fichier XML, profil local, warnings;
- nav sticky: Lecture, Marqueurs, Analyse, Export;
- slider lissage 0-60 s;
- filtres phase;
- pas d'upload XML dans React Lot 2: l'import/matching reste dans l'app Python.
  Le drag & drop XML React pourra revenir seulement si on decide un endpoint
  local d'import dedie. Pour l'instant, React lit le match deja cree.

Lecture:

- 9 graphes;
- graphes conformes a `src/ui/metasoft_graphs.py`, dont `running_economy`;
- paliers de vitesse en fond sur toute la hauteur;
- phases en bande basse;
- valeurs curseur;
- fullscreen par graphe;
- zoom drag Plotly;
- double-clic reset zoom.

Marqueurs:

- click graphe ouvre la popover de pose;
- choix ligne/range;
- drag centre/debut/fin;
- clic droit supprime;
- bouton `Sauvegarder marqueurs` appelle `/markers/officialize`;
- les valeurs confirmees remplacent la preview dans le resume.

Analyse:

- economie de course par palier d'echauffement depuis `analysis.computed.running_economy`;
- graph EC vs vitesse;
- table native DE/DECHO/DEFAT/DEPRO si disponible;
- warnings explicites, non bloquants sauf erreur API.

Export/report:

- `Previsualiser report profil`: appelle `/profile/report-preview`;
- si conflit: afficher les champs en conflit et demander confirmation;
- `Reporter au profil`: appelle `/profile/report`, avec `conflict_policy:
  overwrite` seulement apres confirmation utilisateur;
- `Exporter JSON Valentin`: appelle `/export`;
- afficher chemins locaux JSON + sidecar audit retournes par Python.

## Decisions UX

- Browser par defaut, pas de webview Lot 2.
- Fullscreen = modal CSS locale, pas Radix/shadcn pour eviter d'importer tout le
  design system dashboard.
- CSS autonome dans `local_ui/src/styles.css`, palette Enduraw dark moderne.
- Pas de Tailwind Lot 2: les classes dashboard doivent etre converties en CSS
  simples pour reduire la pile et le packaging.
- Plotly garde `dragmode: "zoom"` et `doubleClick: "reset"`.
- Le zoom doit mettre a jour `xRange` via `onRelayout`; relachement de drag doit
  conserver le zoom.

## Performance

- Ne pas recalculer `smoothSeries` a chaque mousemove.
- `useMemo` pour `points`, series lissees, shapes et annotations.
- Lissage sliding window O(n), pas O(n*w).
- Pas d'API pendant drag/hover.
- Les 20 MB XML sont deja parses cote Python; React recoit le JSON d'analyse.
  Si payload trop lourd en test reel, Lot 3 ajoutera decimation visuelle cote
  Python tout en gardant points bruts pour officialisation Python.

## Implementation steps

1. Créer le squelette `local_ui` Vite React TypeScript minimal.
2. Ajouter dependencies minimales:
   - `@vitejs/plugin-react`;
   - `typescript`;
   - `vite`;
   - `react`;
   - `react-dom`;
   - `plotly.js-dist-min`;
   - `react-plotly.js`;
   - `lucide-react`.
3. Copier-adapter les types MetaSoft dans `local_ui/src/types/metasoft.ts` pour
   matcher l'API Python locale.
4. Créer `local_ui/src/lib/localApi.ts`.
5. Copier-adapter `graphConfig`, `chartUtils`, `markerUtils`.
   - `graphConfig` doit reprendre les 9 graphes de `src/ui/metasoft_graphs.py`.
   - `markerUtils` peut calculer des valeurs preview pour affichage, mais jamais
     pour l'officialisation ou l'export.
   - ajouter `serializeMarkerSelections`.
6. Adapter `MetaSoftChart`:
   - imports locaux;
   - modal CSS maison;
   - lissage visuel uniquement;
   - fix zoom au relachement;
   - double-clic reset.
7. Créer `App.tsx`:
   - fetch analysis au chargement;
   - gestion `draftMarkers`/`confirmedMarkers`;
   - sections Lecture/Marqueurs/Analyse/Export.
8. Créer composants locaux simples:
   - toolbar;
   - cursor rail;
   - marker panel;
   - analysis/export section.
9. `npm run build`.
10. Verifier que `src/local_api/metasoft_server.py` sert bien
    `local_ui/dist/index.html` et les assets.

## Tests/checks Lot 2

Obligatoires:

- `cd local_ui && npm run build`;
- `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_metasoft*.py'`;
- `git diff --check`;
- smoke browser documente obligatoire. Playwright seulement si deja disponible
  ou si GO explicite; sinon checklist manuelle avec resultat dans le recap
  worker:
  - page `/metasoft?...` charge sans erreur;
  - 9 graphes visibles;
  - le graphe `running_economy` est present;
  - slider lissage modifie l'aspect sans changer les selections envoyees;
  - drag zoom conserve le zoom au relachement;
  - double-clic reset;
  - click pose SV1 draft;
  - `Sauvegarder marqueurs` renvoie valeurs Python;
  - apres modification d'un marqueur sauvegarde, l'UI signale `needsSave` ou
    invalide la valeur confirmee;
  - report preview conflit fonctionne;
  - export ecrit JSON + sidecar local.

## Audit Lot 2

L'audit independant doit verifier:

- aucun marqueur officiel calcule cote React;
- aucun champ `values` envoye dans `marker_selections`;
- `serializeMarkerSelections` exclut `values`, `preview`, `smoothed_values`,
  `point_count`, `phase`;
- `confirmedMarkers` ne peut pas rester officiel si `draftMarkers` change;
- les 9 graphes correspondent a `src/ui/metasoft_graphs.py`;
- aucune valeur lissee dans report/export;
- aucun appel API pendant hover/drag/zoom;
- token present sur tous les appels API;
- build Vite servi par Python;
- pas de regression Lot 1 API;
- performance acceptable avec XML reel fourni.

## Hors Lot 2

- icone desktop Enduraw: Lot 4 packaging;
- pywebview/fenetre app integree: seulement apres validation navigateur;
- import XML direct dans React;
- push BDD;
- packaging Windows/Mac final.
