# MetaSoft local UI + export - plan d'execution

Date: 2026-07-08

Ce document est un plan d'implementation. Il ne demande aucun push BDD, aucun
commit et aucune modification hors de l'app locale
`enduraw_testing_tool`.

## Objectif produit exact

Le prochain chantier doit livrer dans l'app Python locale:

1. Visualisation locale des 9 graphes MetaSoft avec une vraie UX claire,
   proche MetaSoft mais avec une direction artistique Enduraw sobre.
2. Lissage reglable par slider, strictement visuel, sans modifier les valeurs
   brutes exportees.
3. Clic exact et annotation des marqueurs `SV1`, `SV2`, `VO2max`, `VMA`,
   avec fenetres ajustables, report dans le profil local
   `stress_test_results`, et alerte non bloquante si identite XML != profil.
4. Graphes et tableaux d'economie de course comme dans la branche dashboard
   P0, avec source, unite et formule explicites.
5. Export JSON complet compatible Valentin: garder le format historique,
   enrichir seulement si necessaire et auditable, sans casser l'export batch.
   Le chantier livre obligatoirement deux sorties locales: JSON principal
   strict compatible Valentin + sidecar audit `.metasoft_audit.json`.

## Garde-fous

- Modifier uniquement les fichiers du chantier pendant l'implementation.
- Ne jamais toucher a
  `/Users/arthurmo/Developer/Enduraw/code/dashboard/backend/activities/router.py`.
- Aucun appel d'ecriture BDD, aucun push prod, aucun push Git sans GO explicite.
- Ne pas ajouter de dependance sans preuve qu'elle evite plus de risque qu'elle
  n'en cree.
- Ne pas stage avec `git add ..`; stage uniquement les fichiers du lot si un GO
  commit arrive plus tard.
- Les XML reels et les outputs de session restent hors Git.
- Le lissage, la decimation et le rendu graphique ne deviennent jamais source
  officielle pour les seuils, marqueurs ou exports.

## Etat actuel verifie

Branche locale inspectee:
`feature/metasoft-local-core`.

Worktree deja sale avant ce plan:

- `run.sh` modifie.
- `src/core/data_transformer.py` modifie.
- `src/utils/xml_parser.py` modifie.
- `docs/metasoft_visualisation_local_migration_plan.md` non suivi.
- `src/core/metasoft_analysis.py` non suivi.
- `src/core/metasoft_markers.py` non suivi.
- `tests/` non suivi.

Ces changements doivent etre consideres comme contexte existant et ne doivent
pas etre revert.

### App locale

Repo:
`/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool`.

Stack actuelle:

- UI desktop: `customtkinter`.
- Graphes deja installes: `matplotlib`.
- Packaging documente: `pyinstaller`.
- Donnees locales: `sessions/<session>/profiles`, `xml`, `matches.json`,
  `output`.
- Lookup Mongo optionnel present dans l'UI, mais le chantier MetaSoft ne doit
  pas ecrire en BDD.

Fichiers utiles verifies:

- `src/main_session.py`
  - pages sidebar: `Sessions`, `Profils`, `XML Matching`;
  - export unitaire `_export_match`;
  - export batch `_export_all_matches`;
  - matching profil/XML;
  - barre Mongo optionnelle.
- `src/ui/app_tabs.py`
  - `MatchListItem` contient deja le bouton `Exporter`;
  - point naturel pour ajouter `Analyser`.
- `src/ui/tabbed_form.py`
  - formulaire profil local;
  - champs `stress_test_results` deja mappes:
    `measured_vo2max`, `max_hr`, `vma`, `sv1_*`, `sv2_*`;
  - rendu matplotlib deja branche pour lactate.
- `src/core/session_manager.py`
  - `get_profile`, `update_profile`, `get_xml_path`, `save_output`;
  - ces helpers suffisent pour reporter les marqueurs et exporter sans nouveau
    stockage central.
- `src/core/profile_template.py`
  - `stress_test_results.thresholds.sv1/sv2`,
    `measured_vo2max`, `max_hr`, `vma`, `first_stage_speed`,
    `last_stage_speed`, `lactate_profile`.
- `src/utils/xml_parser.py`
  - parser Spreadsheet XML avec respect `ss:Index`;
  - payload historique conserve;
  - payload normalise `metasoft_parsed`;
  - labels metriques: `V'O2`, `V'O2/kg`, `V'CO2`, `FC`, `V'E`, `VT`,
    `BF`, `RER`, `v`, `PetO2`, `PetCO2`, `DE`, `DECHO`, `DEFAT`,
    `DEPRO`, `V'E/V'O2`, `V'E/V'CO2`.
- `src/core/metasoft_analysis.py`
  - phases;
  - paliers d'echauffement;
  - baseline repos;
  - EC en `J/kg/m`;
  - `VCO2` natif sinon derive `VO2 * RER`;
  - `DE*` natif en `kcal/h`;
  - warning coherence ventilatoire sans fallback metier.
- `src/core/metasoft_markers.py`
  - calcul officiel des marqueurs sur points bruts;
  - mode point: point XML le plus proche;
  - mode range: moyenne inclusive des points bruts;
  - mapping vers `stress_test_results`;
  - application de patch sur copie du profil.
- `src/core/data_transformer.py`
  - sortie JSON historique via `TestResult`;
  - seuils construits depuis le profil local;
  - graphes exportes depuis points MetaSoft normalises si disponibles;
  - agregation export a 15 s;
  - aucun lissage exporte.
- `tests/test_metasoft_local_core.py`
  - tests parser, EC, marqueurs, patch profil, export graphes sans remplacer
    `None` par `0`.

### Artefacts verifies

XML test:
`/Users/arthurmo/Downloads/TCP__VAN DER VEEN_Noor_2026.06.10_12.38.06_.xml`.

Constats sur ce XML:

- taille: environ 5,85 MB;
- points normalises: 1742;
- athlete XML: `VAN DER VEEN Noor`, poids `68.0 kg`;
- test XML: `2026-06-10T12:38:06`;
- phases: `Repos`, `Echauffement`, `Exercice`, `Retablissement`;
- metriques disponibles: toutes les metriques P0 sauf `vco2_l_min` natif;
- EC actuelle derive donc `VCO2 = VO2 * RER`;
- warning observe: coherence `V'E/(V'E/V'O2)` differente de `V'O2` XML
  d'environ `10,13%`; aucun fallback applique.

JSON exporte observe:
`sessions/2026-07-08_contas/output/Mo_Arthur_2026-07-08.json`.

Constats:

- top-level historique:
  `user_id`, `athlete_name`, `test_date`, `test_type`, `consentements`,
  `seuils`, `protocole`, `test_lactate`, `observations_lactate`,
  `patient_info`, `conseils_entrainements`, `graphiques`, `logos`,
  `partenaires`;
- `graphiques` contient seulement `graphique_1`, `graphique_2`,
  `zones_seuils`;
- pas de marqueurs interactifs sauvegardes;
- pas d'EC exportee;
- `seuils` restent vides si le profil local est vide;
- mismatch volontaire observe: profil local `Mo Arthur`, XML `VAN DER VEEN
  Noor`. Ce cas doit produire une alerte non bloquante, pas bloquer le test.

### Dashboard P0 inspecte

Repo:
`/Users/arthurmo/Developer/Enduraw/code/dashboard`.

References utiles:

- `frontend/src/components/coach-metasoft/graphConfig.ts`
  - liste source des 9 graphes;
  - couleurs marqueurs.
- `frontend/src/components/coach-metasoft/chartUtils.ts`
  - bandes de phase et vitesse;
  - annotations phases, vitesses, marqueurs.
- `frontend/src/components/coach-metasoft/markerUtils.ts`
  - noms marqueurs, fenetre par defaut `120 s`;
  - conversion horloge;
  - moyenne des valeurs brutes.
- `frontend/src/components/coach-metasoft/MetaSoftChart.tsx`
  - plein ecran;
  - series manquantes visibles;
  - lissage O(n) par fenetre temps;
  - vitesse non lissee;
  - clic marqueur, double clic reset, drag centre/bornes, clic droit suppression.
- `backend/coaching/metasoft_export.py`
  - export strict Valentin sans bloc top-level `metasoft_analysis`;
  - validation bloquante des champs requis;
  - `inclinaison_pct = 0` accepte.

Decision importante: ne pas porter l'architecture web dashboard dans l'app
locale au premier lot. L'app locale a deja `customtkinter` et `matplotlib`.
Ajouter React, Plotly, serveur local, `pywebview`, FastAPI ou Flask pour ce
chantier cree une deuxieme pile et complique le packaging Windows/Mac. Garder
une option web seulement si la version native echoue sur l'UX ou la perf.

## Ce qui marche deja

- Parsing XML local robuste enough pour le XML reel inspecte.
- Extraction metriques, unites, phases et points normalises.
- Analyse EC core.
- Calcul marqueurs core sur points bruts.
- Patch de profil local en memoire.
- Export JSON historique sans lissage.
- Export batch existant.
- Tests unitaires core.

## Ce qui manque

- Bouton `Analyser` depuis un match profil/XML.
- Vue locale MetaSoft dans l'app.
- Rendu des 9 graphes.
- Lissage slider.
- Clic exact, popup de choix marqueur, fenetres ajustables.
- VMA comme marqueur disponible dans l'UX.
- Sauvegarde effective du patch dans `profiles/*.json`.
- Alerte non bloquante de mismatch identite XML/profil.
- Tableau de marqueurs avec sources/unites.
- Graphique et tableau EC visibles.
- Warnings visibles.
- Export enrichi/auditable EC sans casser le JSON strict ni le batch.
- Tests d'integration UI/export autour du nouveau flux.

## Architecture cible minimale

Principe Ponytail: livrer la valeur avec la pile deja installee. Pas de serveur
local, pas de navigateur, pas de nouvelle dependance pour le premier chantier.

```text
XML Matching
  MatchListItem
    Exporter
    Analyser

MetaSoftAnalysisWindow (nouvelle fenetre CustomTkinter)
  parse XML via TCPXmlParser
  analyse via metasoft_analysis
  rendu 9 graphes via matplotlib FigureCanvasTkAgg
  slider lissage visuel
  interaction marqueurs
  tableau marqueurs
  tableau EC
  bouton Reporter au profil
  bouton Exporter JSON

core existant
  xml_parser.py              source points + unites
  metasoft_analysis.py       phases + EC + warnings
  metasoft_markers.py        marqueurs officiels + patch profil
  data_transformer.py        JSON Valentin strict
  session_manager.py         lecture/ecriture locale session
```

### Nouveaux modules proposes

Minimum utile:

- `src/ui/metasoft_analysis_window.py`
  - fenetre orchestratrice;
  - chargement match;
  - etat UI;
  - boutons action;
  - pas de calcul metier autre que delegation aux helpers core.
- `src/ui/metasoft_graphs.py`
  - config des 9 graphes;
  - rendu matplotlib;
  - conversion clic -> temps;
  - overlays phases/vitesses/marqueurs;
  - lissage visuel.
- `src/ui/metasoft_tables.py`
  - tableau marqueurs;
  - tableau EC;
  - warnings et sources.

Option encore plus petite si le diff reste lisible: garder
`metasoft_tables.py` integre dans `metasoft_analysis_window.py` au premier lot.
Ne pas depasser un composant geant: si `metasoft_analysis_window.py` approche
800-1000 lignes, extraire.

### Responsabilites

- `xml_parser.py`: lire XML, exposer points, metriques et unites. Pas d'UI.
- `metasoft_analysis.py`: calculer phases, paliers, EC, warnings. Pas d'I/O.
- `metasoft_markers.py`: officialiser un marqueur depuis points bruts et
  produire un patch profil. Pas de widgets.
- `metasoft_graphs.py`: afficher des series et overlays. Calcul lissage visuel
  autorise, calcul officiel interdit.
- `metasoft_analysis_window.py`: relier match, profil, XML, graphes, tables,
  sauvegarde profil et export.
- `data_transformer.py`: rester la sortie officielle du JSON Valentin.
- `SessionManager`: rester l'unique ecriture locale profiles/output.

## Donnees qui circulent

1. `XmlMatchTab` ouvre la fenetre avec `profile_name` et `xml_filename`.
2. La fenetre lit:
   - profil via `session_manager.get_profile(profile_name)`;
   - chemin XML via `session_manager.get_xml_path(xml_filename)`.
3. La fenetre parse:
   - `xml_data = TCPXmlParser().parse_file(xml_path)`;
   - `analysis = xml_data["metasoft_analysis"]`.
4. Si le poids XML est absent et poids profil disponible:
   - recalcul via `build_metasoft_analysis(metasoft_parsed, manual_mass_kg)`.
5. Les graphes lisent `analysis.points`, `analysis.metrics`,
   `analysis.phases`, `analysis.warmup_stages`.
6. Les clics produisent des appels a `build_metasoft_marker(points, name, ...)`.
   Le temps clique vient de la coordonnee x convertie en secondes. La valeur
   officielle vient toujours des points bruts, jamais de la valeur interpolee
   matplotlib, de la courbe lissee ou d'une serie decimee.
7. Les marqueurs valides produisent des patchs via
   `metasoft_marker_to_stress_patch`.
8. `Reporter au profil` applique les patchs via `apply_metasoft_stress_patch`,
   compare les conflits, puis sauvegarde par `session_manager.update_profile`.
9. `Exporter JSON` relit ou utilise le profil a jour, appelle
   `DataTransformer.transform(xml_data, profile_data)`, puis
   `session_manager.save_output`.
10. `Exporter tout` reste le flux existant et beneficie des profils deja
    reportes, sans ouvrir tous les XML.

## Decisions data

### Metriques XML

Chaque metrique affichee doit conserver:

- cle canonique;
- label MetaSoft source;
- unite XML;
- transformation;
- fallback eventuel.

Sources actuelles:

| Cle | Source XML | Unite attendue | Transformation |
| --- | --- | --- | --- |
| `fc_bpm` | `FC` | `/min` ou bpm affiche | native |
| `vo2_l_min` | `V'O2` | `L/min` | native |
| `vo2_ml_kg_min` | `V'O2/kg` | `ml/min/kg` | native |
| `vco2_l_min` | `V'CO2` | `L/min` | native si present |
| `ve_l_min` | `V'E` | `L/min` | native |
| `vt_l` | `VT` | `L` | native |
| `bf_per_min` | `BF` | `/min` | native |
| `rer` | `RER` | sans unite | native |
| `speed_kmh` | `v` | `km/h` | native |
| `peto2_mmhg` | `PetO2` | `mmHg` | native |
| `petco2_mmhg` | `PetCO2` | `mmHg` | native |
| `de_kcal_h` | `DE` | `kcal/h` | native |
| `decho_kcal_h` | `DECHO` | `kcal/h` | native |
| `defat_kcal_h` | `DEFAT` | `kcal/h` | native |
| `depro_kcal_h` | `DEPRO` | `kcal/h` | native |
| `ve_vo2` | `V'E/V'O2` | sans unite | native, controle seulement |
| `ve_vco2` | `V'E/V'CO2` | sans unite | native, controle seulement |

Ne jamais reconstruire `VO2` ou `VCO2` depuis `V'E/(V'E/V'O2)` ou
`V'E/(V'E/V'CO2)` comme fallback metier.

### Economie de course

Formule:

```text
EC = ((0.00055 * (VCO2 - VCO2repos)) + (0.004471 * (VO2 - VO2repos))) * 4184 / (masse * vitesse)
```

Unites:

- `VO2`: `ml/min`;
- `VCO2`: `ml/min`;
- `VO2repos`: `ml/min`;
- `VCO2repos`: `ml/min`;
- `masse`: `kg`;
- `vitesse`: `m/min`;
- sortie: `J/kg/m`.

Sources:

- `VO2` depuis `V'O2` XML en `L/min`, converti en `ml/min`.
- `VCO2` depuis `V'CO2` XML si present, converti en `ml/min`.
- fallback autorise: `VCO2 = VO2 * RER` si `V'CO2` absent et `RER` present;
  marquer `vco2_source = derived_vo2_x_rer`.
- repos depuis phase XML `Repos`.
- masse depuis XML si presente, sinon profil local `body_composition.current_weight`.
- vitesse depuis `v` XML en `km/h`, convertie en `m/min`.

Absences:

- Si repos absent, masse absente, vitesse <= 0, VO2 absent ou VCO2/RER absent:
  EC `None`, warning lisible, pas de valeur inventee.
- Un palier a `0 km/h` ne divise jamais par zero.
- Un palier tres bas garde un warning de qualite.

### Lissage

Le lissage est uniquement une transformation de rendu:

- slider en secondes;
- `0 s` = brut;
- fenetre glissante centree par temps;
- ignorer `None`;
- ne pas lisser `speed_kmh`;
- ne pas ecrire de valeurs lissees dans `analysis`, profil ou JSON;
- ne pas utiliser le lissage pour les marqueurs.

Implementation native recommandee:

- fonction locale dans `metasoft_graphs.py`;
- O(n) par serie comme le dashboard, avec deux pointeurs;
- recalculer seulement les series visibles quand le slider change.

### Marqueurs

Noms officiels:

- `SV1`;
- `SV2`;
- `VO2_max` en code, libelle UI `VO2max`;
- `VMA`.

Modes:

- point: le clic garde `selection_time_seconds`, officialise le point XML brut
  le plus proche;
- fenetre: moyenne inclusive des points bruts entre debut et fin;
- aucune valeur `None` n'est remplacee par `0`.

Mapping profil:

| Marqueur | Source marqueur | Cible profil |
| --- | --- | --- |
| `SV1` | `values.fc_bpm` | `stress_test_results.thresholds.sv1.hr_bpm` |
| `SV1` | `values.speed_kmh` | `stress_test_results.thresholds.sv1.pace_km_h` |
| `SV1` | `values.vo2_ml_kg_min` | `stress_test_results.thresholds.sv1.vo2_ml_kg_min` |
| `SV2` | `values.fc_bpm` | `stress_test_results.thresholds.sv2.hr_bpm` |
| `SV2` | `values.speed_kmh` | `stress_test_results.thresholds.sv2.pace_km_h` |
| `SV2` | `values.vo2_ml_kg_min` | `stress_test_results.thresholds.sv2.vo2_ml_kg_min` |
| `VO2max` | `values.fc_bpm` | `stress_test_results.max_hr` |
| `VO2max` | `values.vo2_ml_kg_min` | `stress_test_results.measured_vo2max` |
| `VMA` | `values.speed_kmh` | `stress_test_results.vma` |

Conflits:

- champ vide: reporter automatiquement;
- champ deja rempli avec meme valeur: rien a demander;
- champ deja rempli avec valeur differente: afficher ancien/nouveau et demander
  confirmation;
- refus: garder le profil, conserver le marqueur uniquement dans la fenetre.

### Identite XML/profil

Comparer:

- XML: `analysis.athlete.last_name`, `first_name`, `athlete_name`;
- profil: `identity.last_name`, `identity.first_name`.

Normalisation:

- trim;
- lowercase;
- enlever accents si simple avec `unicodedata.normalize`;
- comparer les tokens non vides.

Resultat:

- mismatch = bandeau warning non bloquant;
- texte: `XML: VAN DER VEEN Noor / Profil: Mo Arthur`;
- bouton `Continuer quand meme` inutile si le warning n'est pas bloquant;
- export et report profil restent autorises.

## UX precise

### Entree dans l'app

Dans `XML Matching`, chaque association doit afficher:

- `Analyser`;
- `Exporter`;
- `X`.

`Exporter tout` reste au niveau global et ne lance pas l'analyse UI.

Au clic `Analyser`:

1. ouvrir une fenetre `MetaSoft - <profil> / <xml>`;
2. parser l'XML une seule fois;
3. afficher un etat de chargement;
4. afficher warnings non bloquants en haut;
5. charger les graphes et tableaux.

### Layout fenetre MetaSoft

Structure proposee:

```text
Header
  nom XML / nom profil / date test / taille fichier
  warning mismatch identite si besoin
  warning donnees MetaSoft

Toolbar
  slider lissage: 0 s, 15 s, 30 s, 60 s, 120 s, 240 s
  filtre phase: Tout, Repos, Echauffement, Exercice, Retablissement
  bouton reset zoom
  bouton Reporter au profil
  bouton Exporter JSON

Body
  gauche: liste compacte des 9 graphes
  centre: graphe actif grand
  droite: panneau marqueurs + EC + sources/warnings

Footer optionnel
  dernier point survole / temps / phase / valeurs principales
```

Si ce layout prend trop de code en CustomTkinter, V1 acceptable:

- grille 3 x 3 de graphes mini;
- clic sur un graphe ouvre un plein ecran `CTkToplevel`;
- panneau marqueurs et EC sous la grille.

### Les 9 graphes

Configuration reprise du dashboard:

1. `FC + V'O2`
   - `fc_bpm` en bpm;
   - `vo2_l_min` en `L/min`.
2. `V'O2/kg + vitesse`
   - `vo2_ml_kg_min` en `ml/min/kg`;
   - `speed_kmh` en `km/h`.
3. `V'E + BF`
   - `ve_l_min` en `L/min`;
   - `bf_per_min` en `/min`.
4. `RER`
   - `rer`, sans unite.
5. `V'E/V'O2 + V'E/V'CO2`
   - ratios sans unite.
6. `PetO2 + PetCO2`
   - `mmHg`.
7. `DE / DECHO / DEFAT / DEPRO`
   - `kcal/h`;
   - valeurs MetaSoft natives uniquement.
8. `Economie de course`
   - barres ou points par palier;
   - `J/kg/m`;
   - annoter vitesse palier.
9. `Synthese seuils`
   - graph principal `FC + V'O2`;
   - overlays marqueurs;
   - tableau synthetique adjacent si plus lisible en matplotlib.

Pour chaque graphe:

- afficher les series disponibles;
- afficher `Absent XML: <series>` si certaines manquent;
- si aucune serie du graphe n'existe, afficher un etat vide non bloquant;
- overlays phases en bas;
- bandes de vitesse si `speed_kmh` disponible;
- marqueurs communs visibles sur tous les graphes;
- plein ecran par graphe;
- zoom/pan utilisable au minimum sur le graphe actif et le plein ecran;
- reset zoom par double clic si fiable avec matplotlib, sinon par bouton
  visible `Reset zoom`.

### Interactions graphes

Minimum V1:

- clic gauche dans le graphe: popup ou panneau "Placer marqueur";
- conversion x-coordinate -> `t_seconds` avant tout calcul officiel;
- officialisation uniquement via `build_metasoft_marker(points, ...)` sur les
  points bruts MetaSoft;
- interdiction d'utiliser la valeur y sous la souris, la courbe lissee ou une
  interpolation matplotlib pour les valeurs officielles;
- choix marqueur: `SV1`, `SV2`, `VO2max`, `VMA`;
- choix mode: `Point` ou `Fenetre`;
- duree fenetre par defaut: `4:00` centree sur le clic;
- champs debut/fin en `h:mm:ss`;
- bouton recalculer si debut/fin edits manuelles;
- bouton supprimer marqueur;
- zoom/pan fonctionnel sur le graphe actif/fullscreen;
- reset zoom par double clic ou, si double clic matplotlib non fiable, bouton
  `Reset zoom`.

UX avancee a faire dans le meme chantier si cout raisonnable:

- drag de la ligne centre;
- drag des bornes debut/fin;
- clic droit sur marqueur pour supprimer;
- synchronisation curseur sur tous les graphes.

Si matplotlib rend le drag fragile, ne pas bloquer le chantier: les champs
debut/fin editables couvrent l'objectif "fenetres ajustables". Marquer dans
le code `# ponytail: drag precis reporte si matplotlib devient fragile; champs
debut/fin couvrent l'ajustement officiel.`

### Tableau marqueurs

Colonnes:

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
- source officielle: `point_brut` ou `moyenne_fenetre_brute`;
- statut/warning.

### Tableau EC

Colonnes:

- palier;
- debut;
- fin;
- vitesse `km/h`;
- vitesse `m/min`;
- points;
- EC `J/kg/m`;
- VO2 moyen `ml/min`;
- VCO2 moyen `ml/min`;
- source VCO2;
- masse `kg`;
- source masse;
- DE, DECHO, DEFAT, DEPRO `kcal/h` si presents;
- warning.

Sous le tableau, afficher la formule EC et les sources:

```text
EC = ((0.00055 * (VCO2 - VCO2repos)) + (0.004471 * (VO2 - VO2repos))) * 4184 / (masse * vitesse)
VO2/VCO2 en ml/min, masse en kg, vitesse en m/min, sortie en J/kg/m.
```

## Export

### Regle de compatibilite Valentin

Le JSON principal doit garder les top-level historiques:

```text
user_id
athlete_name
test_date
test_type
consentements
seuils
protocole
test_lactate
observations_lactate
patient_info
conseils_entrainements
graphiques
logos
partenaires
```

Ne pas ajouter de top-level `metasoft_analysis` au JSON principal.

### Decision export: deux sorties locales

Le chantier doit produire deux fichiers a chaque export unitaire depuis la
fenetre MetaSoft:

1. JSON principal strict compatible Valentin.
   - meme top-level historique;
   - `graphique_1`, `graphique_2`, `zones_seuils` conserves;
   - seuils remplis via le profil local apres report marqueurs;
   - aucune donnee lissee;
   - aucun top-level `metasoft_analysis`.
2. Sidecar audit obligatoire:
   - nom: `output/<nom>_<date>.metasoft_audit.json`;
   - contenu: marqueurs, fenetres, valeurs officielles, EC, warnings, sources,
     unites, formule, metadonnees XML/profil/export;
   - peut contenir des points decimes pour audit visuel si utile;
   - ne contient jamais les series lissees;
   - n'est pas le payload envoye a Valentin tant que son ingestion n'est pas
     validee.

Cette strategie evite de casser le script Valentin tout en livrant un export
complet auditable pour Arthur et les coachs.

### Option JSON principal a valider

L'ajout de l'EC dans le JSON principal est optionnel, pas bloquant pour le
chantier. Il ne doit etre active que si Valentin confirme que son script tolere
une sous-cle supplementaire dans `graphiques`.

Option possible:

1. Garder `graphiques.graphique_1`, `graphiques.graphique_2`,
   `graphiques.zones_seuils` strictement compatibles.
2. Ajouter l'EC sous:

```text
graphiques.economie_course
  titre
  unite
  formule
  sources
  paliers[]
```

3. Ne pas ajouter les points bruts complets dans le JSON principal.
4. Si la compatibilite reste incertaine, garder l'EC uniquement dans le sidecar
   obligatoire.

### Contenu EC si ajoute au JSON principal

Structure auditable:

```json
{
  "titre": "Economie de course",
  "unite": "J/kg/m",
  "formule": "((0.00055 * (VCO2 - VCO2repos)) + (0.004471 * (VO2 - VO2repos))) * 4184 / (masse * vitesse)",
  "sources": {
    "vo2": "V'O2 XML, L/min -> ml/min",
    "vco2": "V'CO2 XML si present, sinon VO2 * RER",
    "repos": "phase XML Repos",
    "masse": "XML, sinon profil local",
    "vitesse": "v XML, km/h -> m/min"
  },
  "paliers": [
    {
      "stage_index": 1,
      "speed_kmh": 9.0,
      "speed_m_min": 150.0,
      "value_j_kg_m": 3.512,
      "point_count": 170,
      "vo2_ml_min": 2128.214,
      "vco2_ml_min": 1885.336,
      "vco2_source": "derived_vo2_x_rer",
      "mass_kg": 68.0,
      "native_de": {
        "de_kcal_h": {"value": 622.255, "unit": "kcal/h", "source": "xml_native"}
      },
      "warning": null
    }
  ]
}
```

Si une valeur est absente:

- garder `null`;
- inclure warning;
- ne jamais mettre `0` pour "absent".

### Marqueurs dans export

Le JSON principal obtient les seuils via le profil local apres report:

- `DataTransformer._build_seuils` continue a lire `stress_test_results`;
- les marqueurs interactifs ne doivent pas etre une deuxieme source
  concurrente dans `DataTransformer`;
- `zones_seuils` peut etre reconstruit depuis les seuils comme aujourd'hui.

L'audit marqueurs est obligatoire dans le sidecar. Il ne va pas dans le JSON
principal tant que Valentin n'a pas valide un champ dedie.

### Sidecar audit obligatoire

Structure cible minimale:

```text
export
  generated_at
  app_version
  json_filename
  audit_filename
xml
  filename
  size_bytes
  athlete
  test
profile
  filename
  identity
  identity_mismatch_warning
metrics
  <metric_key>: source_label, unit, source, transform
markers
  SV1/SV2/VO2_max/VMA
    mode
    selection_time_seconds
    source_point_t_seconds
    window_start_seconds
    window_end_seconds
    point_count
    values
    official_source
running_economy
  formula
  units
  rest_baseline
  stages
warnings
  parser/analyse/export/profile warnings
audit_points
  optional decimated raw points for visual audit, no smoothed values
```

Regles:

- `markers.*.values` vient de `build_metasoft_marker`.
- `running_economy.stages` vient de `analysis.computed.running_economy`.
- `metrics` vient de `analysis.metrics`.
- `audit_points` est optionnel et decime pour taille; si present, il conserve
  seulement temps, phase et valeurs brutes utiles.
- aucune valeur lissee n'est ecrite dans le sidecar.
- le sidecar doit etre genere aussi si le JSON principal reste strict sans EC.

### Export batch

Ne pas modifier le comportement fonctionnel de `_export_all_matches`:

- il parse chaque XML et transforme chaque profil comme aujourd'hui;
- il ne lance pas la fenetre MetaSoft;
- il ne calcule pas de marqueurs interactifs;
- il profite seulement des valeurs deja reportees dans les profils;
- il ne genere pas obligatoirement de sidecar si l'analyse UI n'a pas ete
  ouverte, sauf decision explicite ulterieure.

Ajouter une validation non bloquante possible:

- si un profil n'a pas de `SV1/SV2/VO2max/VMA`, garder l'export actuel mais
  afficher l'erreur/warning existant;
- ne pas faire echouer les autres matches.

## Plan sequentiel A-Z

### Lot 0 - Verrouiller le scope

Objectif: eviter un chantier qui part en mini-dashboard.

Actions:

1. Relire `git status`.
2. Confirmer que la branche de travail est `feature/metasoft-local-core`.
3. Ne modifier que les fichiers du lot.
4. Lancer les tests core existants avant changement.

Checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_local_core.py
PYTHONDONTWRITEBYTECODE=1 python -m compileall main.py src tests
```

### Lot 1 - Config graphes et lissage natif

Write scope:

- `src/ui/metasoft_graphs.py`
- tests unitaires possibles dans `tests/test_metasoft_local_core.py` ou
  `tests/test_metasoft_ui_helpers.py`

Travail:

1. Definir `GRAPH_CONFIGS` Python a partir du dashboard.
2. Definir couleurs sobres Enduraw:
   - fond sombre existant;
   - lignes nettes;
   - marqueurs `SV1`, `SV2`, `VO2max`, `VMA` repris du dashboard.
3. Ecrire `smooth_series_by_time(times, values, window_seconds)`.
4. Ne pas lisser `speed_kmh`.
5. Retourner les series brutes/lissees pour rendu sans toucher `analysis`.
6. Ajouter un test sur:
   - `0s` retourne brut;
   - `None` ignore;
   - fenetre centree;
   - vitesse non lissee par le renderer/config.

Decision: pas de nouvelle dependance graphique.

### Lot 2 - Export audit sidecar

Write scope:

- `src/core/metasoft_audit_export.py`
- `tests/test_metasoft_local_core.py` ou `tests/test_metasoft_audit_export.py`

Travail:

1. Construire un helper pur `build_metasoft_audit_export(...)`.
2. Entrees:
   - `analysis`;
   - profil local;
   - marqueurs courants;
   - metadata export: noms fichiers, timestamp, warnings UI.
3. Sortie:
   - dict sidecar conforme a la section "Sidecar audit obligatoire".
4. Garantir que le sidecar contient:
   - marqueurs;
   - EC;
   - warnings;
   - sources/unites/formule;
   - mismatch identite si present;
   - aucun lissage.
5. Ajouter une fonction de nommage:
   - `<json_stem>.metasoft_audit.json`.
6. Tests:
   - pas de top-level historique impose ici;
   - marqueurs presents;
   - EC presente avec formule;
   - aucune cle `smoothed` ou `smoothed_values`;
   - `audit_points` absent ou decime.

Ce lot peut etre fait en parallele du Lot 1: il ne touche pas l'UI.

### Lot 3 - Fenetre MetaSoft lecture seule

Write scope:

- `src/ui/metasoft_analysis_window.py`
- `src/main_session.py`
- `src/ui/app_tabs.py`

Travail:

1. Ajouter bouton `Analyser` dans `MatchListItem`.
2. Ajouter callback `on_analyze` depuis `XmlMatchTab`.
3. Dans `_analyze_match`, charger profil + XML, ouvrir `MetaSoftAnalysisWindow`.
4. La fenetre parse l'XML une fois et affiche:
   - header;
   - warnings;
   - slider lissage;
   - 9 graphes ou etats absents;
   - graphe actif et/ou plein ecran;
   - zoom/pan;
   - reset zoom par double clic ou bouton.
5. Afficher mismatch identite XML/profil en warning non bloquant.
6. Brancher les helpers du Lot 1, sans recalcul metier dans la fenetre.

Checks manuels:

- ouvrir session `2026-07-08_contas`;
- analyser `forms_Mo/Arthur` contre XML VAN DER VEEN;
- verifier que le warning mismatch apparait et que la fenetre reste utilisable.
- verifier zoom/pan sur graphe actif ou plein ecran;
- verifier reset zoom par double clic ou bouton.

### Lot 4 - Interactions marqueurs et report profil

Write scope:

- `src/ui/metasoft_analysis_window.py`
- `src/ui/metasoft_tables.py` si extrait
- tests core si helper pur ajoute

Travail:

1. Clic sur graphe -> temps exact via coordonnee axe x.
2. Convertir cette coordonnee x en secondes.
3. Appeler exclusivement `build_metasoft_marker(points, ...)` sur les points
   bruts pour officialiser les valeurs.
4. Ne jamais lire la valeur y matplotlib, la serie lissee ou une interpolation
   comme source officielle.
5. Popup/panneau choix:
   - marqueur;
   - point/fenetre;
   - duree fenetre.
6. Afficher marqueur sur tous les graphes.
7. Tableau marqueurs mis a jour.
8. Edition debut/fin en `h:mm:ss`.
9. Suppression marqueur.
10. Drag des fenetres si cout raisonnable; sinon champs editables couvrent V1.
11. Pour chaque marqueur valide, construire patch via
   `metasoft_marker_to_stress_patch`.
12. Fusionner les patchs dans un patch global.
13. Comparer patch et profil actuel.
14. Si conflit:
   - afficher ancien/nouveau;
   - demander confirmation.
15. Appliquer via `apply_metasoft_stress_patch`.
16. Sauvegarder via `session_manager.update_profile(profile_name, updated)`.
17. Rafraichir formulaire profil si possible quand la page `Profils` est
   ouverte; sinon signaler `Profil sauvegarde`.

Checks:

- point `SV1` garde le temps clique mais officialise le point brut proche;
- fenetre `SV2` moyenne plusieurs points;
- `VO2max` reporte FC + VO2/kg;
- `VMA` reporte vitesse;
- lissage slider ne change pas les valeurs tableau;
- `stress_test_results.thresholds.sv1/sv2` sauvegardes;
- `measured_vo2max`, `max_hr`, `vma` sauvegardes;
- valeurs existantes non ecrasees sans confirmation;
- profil original non mutile si patch bloque.

### Lot 5 - EC visible et export depuis la fenetre

Write scope:

- `src/ui/metasoft_analysis_window.py`
- `src/ui/metasoft_tables.py`
- `src/core/data_transformer.py` seulement si option JSON principal activee
- eventuellement `src/core/metasoft_analysis.py` si source masse doit etre
  exposee plus explicitement
- tests core

Travail:

1. Afficher graph EC par palier.
2. Afficher tableau EC complet.
3. Afficher formule et sources.
4. Brancher bouton `Exporter JSON + audit`.
5. Generer le JSON principal via `DataTransformer`.
6. Generer le sidecar via `build_metasoft_audit_export`.
7. Sauvegarder les deux fichiers via `SessionManager`.
8. Ajouter `mass_source` dans l'analyse si absent:
   - `xml`;
   - `manual_profile`;
   - `missing`.
9. Ne pas changer la formule sans test.
10. L'ajout `graphiques.economie_course` dans le JSON principal reste optionnel
    et ne doit pas bloquer la livraison du sidecar.

Checks:

- XML VAN DER VEEN montre EC sur 4 paliers;
- `vco2_source = derived_vo2_x_rer`;
- `DE*` natifs visibles en `kcal/h`;
- warning coherence ventilatoire visible;
- deux fichiers crees: `.json` + `.metasoft_audit.json`.

Tests:

- top-level JSON identique a l'historique;
- `graphique_1`, `graphique_2`, `zones_seuils` presents;
- sidecar contient marqueurs, EC, warnings, sources, unites, formule;
- EC dans JSON principal seulement si option validee;
- absence EC garde `None`/warning, pas `0`;
- batch export fonctionne avec un match sans marqueurs;
- aucune donnee lissee dans JSON ou sidecar.

### Lot 6 - QA, smoke et perf

Write scope:

- aucun fichier code sauf corrections ciblees.

Checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_local_core.py
PYTHONDONTWRITEBYTECODE=1 python -m compileall main.py src tests
git diff --check
```

Smoke manuel:

1. Lancer `python main.py`.
2. Ouvrir `2026-07-08_contas`.
3. Ouvrir `XML Matching`.
4. Cliquer `Analyser`.
5. Verifier 9 graphes, warnings, slider lissage.
6. Zoomer/panner le graphe actif ou fullscreen.
7. Reset zoom par double clic ou bouton.
8. Placer `SV1`, `SV2`, `VO2max`, `VMA`.
9. Reporter au profil.
10. Reouvrir le profil et verifier les champs.
11. Exporter unitaire.
12. Verifier creation JSON principal + sidecar `.metasoft_audit.json`.
13. Exporter batch.
14. Comparer JSON avant/apres:
    - top-level stable;
    - seuils remplis;
    - graphes historiques presents;
    - EC dans JSON principal seulement si activee.
15. Comparer sidecar:
    - marqueurs presents;
    - EC presente;
    - warnings/sources/unites/formule presents;
    - aucune donnee lissee.

Perf:

- mesurer temps parse + rendu XML VAN DER VEEN 5,85 MB;
- tester avec XML proche 20 MB si disponible;
- objectif PC moyen:
  - parse/analyse sous quelques secondes;
  - fenetre reactive apres rendu;
  - slider lissage sans freeze long;
  - ne charger qu'un XML a la fois;
  - fermer la fenetre libere figures matplotlib.

## Dispatch subagents recommande

Sequence concrete pour limiter les conflits:

1. Subagent graph helpers.
   - scope exclusif: `src/ui/metasoft_graphs.py` + tests helper;
   - livre config 9 graphes, lissage, zoom helpers si purs, conversion temps;
   - ne touche pas `metasoft_analysis_window.py`.
2. Subagent export/audit sidecar, en parallele du 1.
   - scope exclusif: `src/core/metasoft_audit_export.py` + tests;
   - livre le dict sidecar et le nommage `.metasoft_audit.json`;
   - ne touche pas UI, `main_session.py`, ni `data_transformer.py`.
3. Subagent window/read UI, apres merge des lots 1 et 2.
   - scope: `src/ui/metasoft_analysis_window.py`, `src/main_session.py`,
     `src/ui/app_tabs.py`;
   - livre ouverture match, lecture XML/profil, 9 graphes, slider, zoom/reset,
     warnings et EC lecture seule;
   - ne touche pas la logique marqueurs/profil sauf placeholders.
4. Subagent markers/profile, apres le 3.
   - scope principal: `src/ui/metasoft_analysis_window.py`;
   - scope core seulement si helper conflit vraiment necessaire;
   - livre clic exact, fenetres, report profil, confirmations.
5. Subagent QA/export final, apres le 4.
   - scope: corrections ciblees + tests;
   - branche bouton export JSON + sidecar si pas deja fait;
   - valide batch, smoke, perf.

Regles de merge:

- Un seul subagent a la fois modifie `metasoft_analysis_window.py`.
- `metasoft_graphs.py` et `metasoft_audit_export.py` doivent etre merges avant
  le gros lot window.
- `data_transformer.py` ne bouge que si l'option `graphiques.economie_course`
  est explicitement activee; sinon le sidecar suffit pour l'audit complet.

## Tests et checks attendus

### Unitaires core

Conserver et etendre `tests/test_metasoft_local_core.py`:

- parser `ss:Index`;
- metriques et unites;
- EC avec `VO2 L/min -> ml/min`;
- `VCO2` natif puis fallback `VO2 * RER`;
- absence repos/masse/vitesse -> warning + `None`;
- marqueur point;
- marqueur fenetre;
- marqueur ignore lissage;
- patch profil preserve valeurs hors patch;
- conflit profil si helper ajoute.

### Integration export

Tests sur `DataTransformer`:

- top-level historique stable;
- `graphiques.graphique_1/2/zones_seuils` stables;
- EC dans JSON principal seulement si option validee;
- pas de `metasoft_analysis` top-level;
- `None` reste `None`;
- batch compatible avec profil vide.

Tests sur le sidecar:

- fichier `.metasoft_audit.json` cree sur export unitaire depuis la fenetre;
- marqueurs `SV1`, `SV2`, `VO2_max`, `VMA` presents si poses;
- chaque marqueur expose mode, temps, fenetre, points et valeurs officielles;
- EC expose formule, unites, baseline repos, paliers et sources;
- warnings parser/analyse/export/profil presents;
- aucune cle ou valeur lissee exportee.

### UI smoke manuel

Pas besoin d'automatiser CustomTkinter en P0. Le smoke manuel ci-dessus est le
minimum utile. Si une logique UI devient pure, la tester hors Tkinter.

### Critere final Arthur

Apres build/lancement via l'icone ou le lanceur local prevu, Arthur doit pouvoir
faire cette sequence sans terminal et sans BDD:

1. Ouvrir une session existante.
2. Ouvrir un match profil/XML.
3. Voir les 9 graphes MetaSoft ou leurs etats `Absent XML`.
4. Regler le lissage au slider sans changer les valeurs officielles.
5. Zoomer/panner le graphe actif ou fullscreen.
6. Reset zoom par double clic ou bouton.
7. Poser `SV1`, `SV2`, `VO2max`, `VMA`.
8. Ajuster les fenetres.
9. Reporter les valeurs dans `stress_test_results`.
10. Voir le warning mismatch identite XML/profil sans blocage.
11. Exporter le JSON principal compatible Valentin.
12. Exporter le sidecar `.metasoft_audit.json` avec marqueurs, EC, warnings,
    sources et unites.

### Perf XML 20 MB

Script manuel temporaire possible hors Git ou commande directe:

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
import sys, time
sys.path.insert(0, "src")
from utils.xml_parser import TCPXmlParser
p = "/path/to/20mb.xml"
t = time.perf_counter()
d = TCPXmlParser().parse_file(p)
print(len(d["metasoft_analysis"]["points"]), round(time.perf_counter() - t, 2))
PY
```

Ne pas commiter le XML ni un output prive.

## Risques et reponses

- Risque: matplotlib n'offre pas une UX aussi fluide que Plotly.
  Reponse: V1 native d'abord; champs debut/fin remplacent le drag si besoin.
  Passer a web local seulement si une limitation concrete bloque le produit.
- Risque: `metasoft_analysis_window.py` devient un composant geant.
  Reponse: extraire graphes et tables, garder le calcul dans core.
- Risque: export EC casse le script Valentin.
  Reponse: top-level strict; enrichissement sous cle existante seulement apres
  validation; sidecar audit obligatoire dans tous les cas pour l'export complet.
- Risque: mismatch identite bloque Arthur pendant les tests.
  Reponse: warning non bloquant obligatoire.
- Risque: lissage contamine les marqueurs.
  Reponse: marqueurs appellent uniquement `build_metasoft_marker(points, ...)`
  sur points bruts; test dedie.
- Risque: session 30-40 XML lente.
  Reponse: analyse unitaire, pas de preparse global, batch export conserve.
- Risque: XML sans `V'CO2`.
  Reponse: fallback auditable `VO2 * RER`; source affichee.
- Risque: champs profil deja remplis.
  Reponse: confirmation avant overwrite.

## Questions restantes

Hypotheses a garder explicites sans bloquer le chantier:

- Valentin accepte-t-il `graphiques.economie_course` dans le JSON principal ?
  Hypothese de travail: non requis pour livrer; sidecar audit obligatoire.
- La V1 doit-elle obligatoirement avoir drag souris des bornes, ou les champs
  debut/fin suffisent-ils pour "fenetres ajustables" ?
  Hypothese de travail: champs debut/fin suffisent, drag si peu couteux.
- Faut-il persister les marqueurs hors profil pour audit/reouverture ?
  Hypothese de travail: oui pour audit export via sidecar; pas de persistance
  de brouillon/reouverture hors sidecar en P0.
- Faut-il une fenetre repos override pour EC ?
  Hypothese de travail: non en premier lot; phase XML `Repos` fiable, override
  plus tard si coach signale un cas mauvais.
- Le protocole doit-il etre enrichi maintenant avec `inclinaison_pct`,
  `increment_vitesse_kmh`, `duree_palier_min` ?
  Hypothese de travail: documenter comme manque export, mais ne pas bloquer la
  visualisation MetaSoft sauf validation Valentin.
