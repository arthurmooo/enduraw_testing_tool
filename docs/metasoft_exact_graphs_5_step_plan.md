# Plan 5 etapes - Alignement graphes MetaSoft local

Date: 2026-07-08
Branche: `feature/metasoft-react-local-ui`
Repo: `/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool`

## Decisions verrouillees

- L'interface locale React/Python reste la cible: calculs en local, pas de surcharge dashboard serveur.
- Les ajouts Enduraw restent dans l'experience graphes: phases, paliers vitesse en background, lissage, curseur, marqueurs, fullscreen, economie de course.
- L'economie de course ne remplace aucun graphe MetaSoft. Elle reste visible comme ajout Enduraw dans la zone graphes/analyse locale.
- La logique clic locale n'est pas exactement celle de `dashboard-trainer-tools`: cette branche est surtout un rendu Plotly Python/JS statique. La logique locale est plus proche du dashboard courant `frontend/src/components/coach-metasoft/MetaSoftChart.tsx`, avec des divergences a corriger.
- `V'CO2` est absent nativement dans les XML audites. Pour les graphes MetaSoft qui en ont besoin, le fallback autorise est explicite: `V'CO2 derive = V'O2 * RER`, jamais masque comme valeur XML native.

## Grille MetaSoft cible

| # | Graphe MetaSoft | Type | Axe X | Axe Y / series | Source et unite | Etat local actuel |
|---|---|---|---|---|---|---|
| 1 | `V'E` | temps | temps | `V'E` | XML `V'E`, L/min | faux: combine avec BF |
| 2 | `HR, V'O2/HR` | temps double axe | temps | `FC`, `V'O2/FC` | XML `FC` /min, XML `V'O2/FC` ml | manquant |
| 3 | `V'O2, V'CO2` | temps | temps | `V'O2`, `V'CO2` | XML `V'O2` L/min, `V'CO2` derive L/min | manquant/partiel |
| 4 | `V'E(V'CO2)` | scatter | `V'CO2` | `V'E` | `V'CO2` derive L/min, XML `V'E` L/min | manquant |
| 5 | `V'CO2, HR` | scatter | probablement `V'O2` | `V'CO2`, `FC` | XML `V'O2`, `V'CO2` derive, XML `FC` | manquant |
| 6 | `V'E/V'O2, V'E/V'CO2` | temps | temps | ratios ventilatoires | XML natif, sans unite | present mais a aligner |
| 7 | `VT(V'E)` | scatter | `V'E` | `VT` | XML `V'E` L/min, XML `VT` L | manquant |
| 8 | `RER` | temps | temps | `RER` | XML natif, sans unite | present |
| 9 | `PETO2, PETCO2` | temps | temps | `PetO2`, `PetCO2` | XML natif, mmHg | present mais a aligner |

Point a verifier visuellement pendant implementation: le panneau 5 `V'CO2, HR` doit reprendre exactement l'abscisse MetaSoft visible sur la capture. L'hypothese la plus probable est `V'O2` en X, mais elle doit etre confirmee par comparaison avec la capture avant merge final.

## Plan en 5 etapes

### 1. Verrouiller la config des graphes MetaSoft

Remplacer la config P0 actuelle par une config declarative qui porte:
- `kind`: `time` ou `scatter`;
- `xKey`, `xLabel`, `xUnit`;
- `series`, axes, couleurs, source;
- politique d'absence de donnees.

Fichiers probables:
- `local_ui/src/lib/graphConfig.ts`
- `local_ui/src/types/metasoft.ts`
- `src/ui/metasoft_graphs.py` si la config Python miroir reste necessaire.

Validation:
- les 9 graphes MetaSoft apparaissent dans le meme ordre que MetaSoft Studio;
- aucun graphe Enduraw ne supprime un graphe MetaSoft.

### 2. Etendre le contrat data minimal

Ajouter uniquement les champs necessaires:
- `vo2_hr_ml` ou alias propre vers XML `V'O2/FC`;
- `vco2_l_min` derive si absent: `vo2_l_min * rer`;
- metadata de source pour `V'CO2`: `xml` ou `derived_vo2_x_rer`.

Ne pas inventer `%BR`, `BR`, ou `HR` si absents. `HR` UI = `FC` XML, avec libelle MetaSoft si besoin.

Fichiers probables:
- `src/utils/xml_parser.py`
- `src/core/metasoft_analysis.py`
- `local_ui/src/types/metasoft.ts`
- tests core existants.

Validation:
- source, unite, transformation et fallback documentes dans le code ou le payload;
- warning explicite si `V'CO2` derive est utilise;
- aucun fallback silencieux.

### 3. Adapter le rendu React aux graphes temps + scatter

Faire evoluer `MetaSoftChart` pour lire les axes depuis la config:
- graphe temps: X = temps, overlays phases/paliers vitesse/marqueurs visibles;
- scatter: X/Y physiologiques, marqueurs SV conserves si representables, sinon valeurs au curseur et seuils affiches sans fausse verticalite temporelle;
- lissage applique uniquement aux series temporelles ou explicitement autorise, pas aux scatter bruts si cela deforme la relation.

Fichiers probables:
- `local_ui/src/components/MetaSoftChart.tsx`
- `local_ui/src/lib/chartUtils.ts`
- `local_ui/src/components/CursorRail.tsx` si nouveaux champs affiches.

Validation:
- les axes et unites correspondent a la capture MetaSoft;
- series absentes affichees comme absentes, pas remplacees par zero;
- fullscreen conserve le meme rendu que la carte.

### 4. Corriger la racine clic / zoom / trackpad

Ne pas refaire le patch precedent. La correction doit etre a la racine:
- comparer avec le dashboard courant, pas avec `dashboard-trainer-tools`;
- reprendre le guard local manquant `onWheel={(event) => event.preventDefault()}` si confirme;
- extraire un helper pur de conversion `clientX -> xValue` utilise par clic, drag, fullscreen;
- eviter les chemins divergents entre clic normal, drag de range, double-clic de reset et zoom Plotly;
- tester clic apres zoom et double-clic reset.

Fichiers probables:
- `local_ui/src/components/MetaSoftChart.tsx`
- nouveau test helper si possible, sinon test minimal proche.

Validation:
- un clic simple ouvre la modale de marqueur;
- drag zoom zoome au relachement;
- double-clic dezoome;
- drag de marqueur ne declenche pas la modale;
- point/range reporte la valeur brute Python officielle, pas la valeur lissee.

### 5. Recomposer l'experience graphes sans sortir les ajouts Enduraw

Garder les ajouts Enduraw dans la meme experience:
- paliers vitesse en background sur graphes temps;
- phases MetaSoft;
- lissage;
- cursor rail;
- marqueurs et report profil;
- economie de course visible comme ajout Enduraw adjacent/toggle dans la zone graphes/analyse, sans remplacer un des 9 graphes MetaSoft.

Validation:
- l'EC reste accessible sans aller dans une experience separee;
- la table EC conserve la feature masquer/afficher les lignes individuelles;
- l'export JSON Valentin reste complet selon le contrat actuel, avec warnings data.

## Checks avant GO implementation

- `cd local_ui && npm run build`
- `python -m unittest tests/test_metasoft_ui_helpers.py tests/test_metasoft_local_core.py` ou equivalent disponible dans l'environnement.
- Smoke manuel avec:
  - `/Users/arthurmo/Downloads/TCP__VAN DER VEEN_Noor_2026.06.10_12.38.06_.xml`
  - `/Users/arthurmo/Downloads/Private & Shared-4/Follow up 06 07/TCP__BLANC_Olivier_2026.06.30_12.55.31_.xml`

## Risques ouverts

- Le panneau 5 doit etre confirme visuellement: `V'CO2, HR` semble scatter avec `V'O2` en X, mais l'axe exact doit etre valide sur capture MetaSoft.
- Les graphes scatter ne peuvent pas recevoir les backgrounds temporels de la meme facon que les graphes temps. Il faudra garder les ajouts Enduraw utiles sans mentir sur l'axe.
- Les tests Python n'etaient pas executables au moment du checkpoint local car `pytest` n'etait pas installe dans le venv ni le Python systeme. Preferer `unittest` ou installer l'outil de test dans l'environnement de dev.
