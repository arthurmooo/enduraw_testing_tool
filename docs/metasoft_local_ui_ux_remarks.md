# MetaSoft Local UI/UX - remarques a traiter

Date: 2026-07-09

Document de cadrage UI/UX uniquement. Aucun code applicatif, aucun backend,
aucune BDD, aucun export et aucun calcul MetaSoft ne doivent etre modifies sans
GO explicite.

## Scope

Repo: `/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool`

Branche: `feature/metasoft-react-local-ui`

Surface concernee: UI React locale `local_ui/`.

Objectif: transformer la page actuelle, qui ressemble encore trop a un
dashboard de debug dense, en outil de lecture MetaSoft clair, fiable et
operable.

## Contraintes non negociables

- UI/UX uniquement.
- Ne pas toucher a la logique metier MetaSoft.
- Ne pas modifier les calculs, transformations, exports JSON/audit, endpoints
  ou stockage local sauf demande explicite.
- Ne pas creer de design system parallele.
- Reutiliser les composants, helpers, couleurs et patterns existants quand ils
  suffisent.
- Diff minimal, root cause, pas de patch symptomatique.
- Worktree possiblement sale: ne rien revert, ne stage que le chantier si un GO
  de commit arrive.

## Remarques ajoutees par Arthur

### 1. Tooltip du graphe survole moins clair que les autres

Constat:

- Le tooltip du graphe actuellement hovere n'a pas le meme look que les autres.
- Il faudrait le meme rendu visuel partout.

Cause probable:

- Dans `local_ui/src/components/MetaSoftChart.tsx`, le graphe source du hover
  desactive l'annotation custom via `cursorSourceGraphId === graph.id ? [] :
  buildCursorAnnotations(...)`.
- Les autres graphes affichent donc une annotation sombre custom, tandis que le
  graphe hovere retombe sur le tooltip Plotly natif.

Fichiers concernes:

- `local_ui/src/components/MetaSoftChart.tsx`
- `local_ui/src/lib/metasoftChartHelpers.ts`

Attendu:

- Un seul langage visuel de tooltip.
- Meme contraste, meme typographie, meme structure de contenu.
- Pas de difference perceptible entre graphe source et graphes synchronises.

### 2. Modal/popup de placement de seuil tres faible

Constat:

- La popover "Placer un seuil" est visuellement mauvaise.
- Les choix `Ligne`, `Range`, `Precedent` passent sur deux lignes.
- `VO2max` sort de sa case.
- Le bouton de fermeture `x` est trop brut.

Cause probable:

- `.marker-popover` est limitee a `240px`.
- `.segmented` est en `grid-template-columns: 1fr 1fr`, incompatible avec
  trois choix.
- `.marker-choice-grid` force 4 colonnes dans une largeur trop courte.

Fichiers concernes:

- `local_ui/src/components/MetaSoftChart.tsx`
- `local_ui/src/styles.css`

Attendu:

- Popover plus large et stable.
- Trois modes sur une seule ligne.
- Boutons marqueurs lisibles sans overflow.
- `VO2max` doit tenir dans son bouton.
- Fermeture claire avec icone existante si possible.

### 3. Vitesse affichee deux fois dans les tooltips

Constat:

- `Vitesse` apparait plusieurs fois dans certains tooltips.

Cause probable:

- Chaque serie ajoute sa propre ligne `Vitesse` dans `hovertemplate`.
- Avec `hovermode: "x unified"`, Plotly repete le template pour chaque serie.

Fichiers concernes:

- `local_ui/src/components/MetaSoftChart.tsx`
- possiblement `local_ui/src/lib/metasoftChartHelpers.ts`

Attendu:

- Vitesse affichee une seule fois par tooltip.
- Les valeurs des series restent lisibles et groupees.

### 4. Tooltip du graphe EC illisible

Constat:

- Le tooltip du graphe EC est illisible a cause du contraste.
- Le rendu semble etre le tooltip Plotly blanc par defaut sur UI sombre.

Cause probable:

- `ManualEconomyPlot` n'a pas de `hoverlabel` sombre.
- Le helper `trace()` ne definit pas de `hovertemplate` specifique.

Fichiers concernes:

- `local_ui/src/components/RunningEconomyManualSection.tsx`

Attendu:

- Tooltip EC sombre, lisible, coherent avec le reste.
- Noms de series non tronques si possible.
- Contraste suffisant sur fond sombre.

### 5. Artefact: pas de bouton pour valider et replier

Constat:

- Lorsqu'un artefact est positionne, l'editeur reste ouvert.
- Il n'y a pas de bouton clair pour valider la selection et replier la zone.

Cause probable:

- `handlePlotClick` cree l'exclusion, active `activeExclusionIndex`, puis coupe
  `excludeMode`.
- `ArtifactSliders` ne propose que `Supprimer`.

Fichiers concernes:

- `local_ui/src/components/RunningEconomyManualSection.tsx`
- `local_ui/src/styles.css`

Attendu:

- Ajouter une action explicite du type `Terminer`, `Valider` ou `Replier`.
- L'action replie l'editeur sans changer le calcul.
- Garder l'etat d'artefact visible dans la liste.

### 6. Supprimer `Analyse` de la barre du haut

Constat:

- L'item `Analyse` dans la nav du haut est inutile/bruyant.

Cause probable:

- `NAV_ITEMS` contient `Analyse`, `EC` et `Report`.

Fichier concerne:

- `local_ui/src/App.tsx`

Attendu:

- Retirer `Analyse` de la navigation.
- Conserver l'ancre/section d'analyse si elle reste utile pour le contenu.
- Ne pas toucher au report profil.

## Remarques UI/UX deja auditees

### 7. Barre sticky trop chargee

Constat:

- La barre haute melange navigation, filtres, lissage, paliers vitesse et
  phases.
- L'utilisateur ne distingue pas assez ce qui navigue de ce qui modifie les
  graphes.

Fichier concerne:

- `local_ui/src/App.tsx`
- `local_ui/src/styles.css`

Attendu:

- Separer visuellement navigation et controles de lecture.
- Prioriser les controles qui changent les graphes.
- Reduire la densite du header sticky.

### 8. Grille de graphes trop dense

Constat:

- Les graphes sont affiches en grille 3 colonnes avec hauteur compacte.
- Les axes doubles, phases, vitesses, marqueurs et tooltips rendent chaque
  graphe difficile a lire.

Fichiers concernes:

- `local_ui/src/App.tsx`
- `local_ui/src/components/MetaSoftChart.tsx`
- `local_ui/src/styles.css`

Attendu:

- Une lecture principale plus large.
- La grille complete peut rester secondaire ou repliable.
- Ne pas faire de refonte large sans GO explicite.

### 9. Interactions critiques cachees

Constat:

- Placement de seuil par clic.
- Deplacement par drag.
- Reset par double clic.
- Suppression par clic droit.
- Ces gestes sont peu decouvrables et risques.

Fichiers concernes:

- `local_ui/src/components/MetaSoftChart.tsx`
- `local_ui/src/lib/metasoftChartHelpers.ts`

Attendu:

- Rendre les modes explicites.
- Eviter la suppression directe par clic droit sans garde-fou.
- A minima: aide contextuelle, undo ou confirmation legere.

### 10. Suppression de marqueur trop dangereuse

Constat:

- Le clic droit pres d'un marqueur supprime directement le marqueur.

Fichier concerne:

- `local_ui/src/components/MetaSoftChart.tsx`

Attendu:

- Ne pas supprimer sans feedback recuperable.
- Preferer undo inline ou confirmation legere.

### 11. Accessibilite clavier faible

Constat:

- Les actions critiques reposent sur souris, hover, drag et context menu.
- Pas de voie clavier claire pour placer, ajuster ou supprimer.

Fichiers concernes:

- `local_ui/src/components/MetaSoftChart.tsx`
- `local_ui/src/components/RunningEconomyManualSection.tsx`
- `local_ui/src/styles.css`

Attendu:

- Ajouter des alternatives via controles explicites quand le scope le permet.
- Au minimum, ne pas casser la navigation clavier et ajouter focus visible.

### 12. Focus visible insuffisant

Constat:

- Les boutons ont surtout des styles hover/active.
- Certains inputs suppriment `outline`.

Fichier concerne:

- `local_ui/src/styles.css`

Attendu:

- Ajouter `:focus-visible` coherent sur boutons, inputs, toggles, sliders,
  icones et elements de tableau interactifs.

### 13. Fullscreen incomplet

Constat:

- La modale fullscreen de graphe utilise `role="dialog"` mais ne gere pas assez
  l'experience modale.
- Pas de fermeture Escape visible dans le code.
- Pas de focus trap/restauration de focus.

Fichier concerne:

- `local_ui/src/components/MetaSoftChart.tsx`

Attendu:

- Escape pour fermer.
- Focus initial sur le bouton fermer.
- Retour du focus au bouton d'ouverture si possible.
- Pas de refonte lourde sans GO.

### 14. Statuts trop techniques

Constat:

- `preview`, `needsSave`, `Python`, `Report`, `Overwrite` sont des libelles
  internes.

Fichiers concernes:

- `local_ui/src/components/MarkerPanel.tsx`
- `local_ui/src/App.tsx`

Attendu:

- `preview` -> `Brouillon`
- `needsSave` -> `A reporter`
- `Python` -> `Officiel`
- `Report`/`Overwrite` -> libelles francais utilisateur.

### 15. Report profil pas assez rassurant

Constat:

- Le bouton `Reporter au profil` est fort, mais le resume de ce qui va changer
  est insuffisant.

Fichiers concernes:

- `local_ui/src/components/AnalysisExportSection.tsx`
- possiblement `local_ui/src/App.tsx`

Attendu:

- Avant report: l'utilisateur doit comprendre les marqueurs modifies, EC
  incluse/ecartee, artefacts actifs.
- Ne pas toucher au payload sans demande explicite.

### 16. Table marqueurs trop technique

Constat:

- La table marqueurs est un dump technique de valeurs.
- Elle ne met pas assez en avant l'etat utile: seuil place ou non, brouillon ou
  officiel, impact profil.

Fichier concerne:

- `local_ui/src/components/MarkerPanel.tsx`

Attendu:

- Mieux separer marqueur, source/statut, valeurs utiles.
- Ne pas dupliquer la logique metier.

### 17. Table EC trop dense

Constat:

- La table EC affiche beaucoup de colonnes.
- `JSON` comme titre de colonne est trop technique pour une decision utilisateur.
- Les lignes cliquables ne sont pas evidentes.

Fichier concerne:

- `local_ui/src/components/RunningEconomyManualSection.tsx`

Attendu:

- Renommer `JSON` en decision lisible (`Report`, `Profil`, `Inclure`).
- Rendre les lignes interactives plus claires.
- Garder les valeurs scientifiques stables.

### 18. Mode exclusion artefact pas assez explicite

Constat:

- `Exclure artefact` active un mode, puis le prochain clic sur le graphe cree
  une exclusion.
- Le mode actif n'est pas assez evident.

Fichiers concernes:

- `local_ui/src/components/RunningEconomyManualSection.tsx`
- `local_ui/src/styles.css`

Attendu:

- Etat actif tres visible.
- Instruction courte pendant le mode.
- Bouton annuler le mode.

### 19. Warnings pas assez hierarchises

Constat:

- Les warnings sont listes dans le rail curseur.
- Ils melangent information, qualite de donnees et interpretabilite.

Fichier concerne:

- `local_ui/src/components/CursorRail.tsx`

Attendu:

- Les warnings doivent etre visibles sans envahir.
- Ajouter severite/resume si le backend expose deja assez de donnees.
- Ne pas inventer de classification metier si elle n'existe pas.

### 20. Theme visuel trop uniforme

Constat:

- Beaucoup de surfaces bleu nuit, memes bordures, memes cartes.
- L'ensemble lit comme un dashboard technique, pas encore comme UI Enduraw
  finalisee.

Fichier concerne:

- `local_ui/src/styles.css`

Attendu:

- Garder le theme sombre mais augmenter la hierarchie.
- Reserver l'accent vert/bleu aux actions et donnees utiles.
- Eviter les effets decoratifs gratuits.

### 21. Typographie et chiffres a durcir

Constat:

- Les valeurs numeriques importantes ne sont pas assez systematisees.
- Les titres/labels/control text manquent d'une hierarchie stricte.

Fichiers concernes:

- `local_ui/src/styles.css`
- `local_ui/src/components/CursorRail.tsx`
- tables et panels concernes.

Attendu:

- Chiffres en font mono ou style numerique stable.
- Labels plus courts et coherents.
- Pas de font externe ou dependance nouvelle sans justification.

### 22. Layout responsive a surveiller

Constat:

- La grille bascule en 2 puis 1 colonnes.
- Les panels denses, popovers et tables peuvent encore deborder ou devenir
  trop longs.

Fichier concerne:

- `local_ui/src/styles.css`

Attendu:

- Pas d'overflow horizontal non controle.
- Popovers et tables utilisables a largeur reduite.
- Ne pas optimiser mobile au detriment du poste desktop principal sans GO.

## Ordre de traitement recommande

### Lot 1 - Correctifs UI immediats, diff minimal

1. Retirer `Analyse` de la nav.
2. Unifier les tooltips graphes.
3. Supprimer la repetition de `Vitesse`.
4. Ajouter tooltip EC sombre/lisible.
5. Corriger la popover seuil: largeur, 3 modes en ligne, `VO2max` sans
   overflow.
6. Ajouter `Terminer/Replier` sur l'editeur d'artefact.

## Plan d'execution Lot 1 - GO candidate

Scope strict: correctifs UI immediats uniquement. Pas de changement calcul,
export, parsing XML, payload report, ni modele de donnees. Diff cible sur les
composants React/CSS existants, sans abstraction nouvelle sauf constante locale
si elle retire un magic number lie au layout.

### 1. Nav: retirer `Analyse`

Decision technique exacte:

- Supprimer uniquement l'item `{ label: "Analyse", targetId:
  "metasoft-analysis-export" }` de `NAV_ITEMS`.
- Garder la section DOM `metasoft-analysis-export` et le composant
  `AnalysisExportSection` s'ils restent utilises par le flux report.

Fichiers et fonctions/classes touches:

- `local_ui/src/App.tsx`
  - `NAV_ITEMS`

Invariant a preserver:

- Le bouton `Report` et la section `Report profil` restent accessibles.
- Aucun changement de logique dans `AnalysisExportSection`, `handleReport` ou
  le payload reporte.

Critere d'acceptation testable:

- La barre haute affiche `Lecture`, `Marqueurs`, `EC`, `Report`, sans onglet
  `Analyse`.
- La section d'analyse/export existe encore dans la page si le scroll ou le
  flux `Report` l'utilise.

Risque:

- Faible. Risque principal: un lien d'ancre interne dependrait explicitement de
  cet item de nav. A verifier par lecture des usages de `NAV_ITEMS`.

### 2. Tooltips graphes: une seule strategie visuelle

Decision technique exacte:

- Utiliser l'annotation custom existante comme tooltip unique pour les graphes
  temporels.
- Afficher aussi cette annotation sur le graphe source en supprimant le garde:
  `cursorSourceGraphId === graph.id ? [] : buildCursorAnnotations(...)`.
- Neutraliser le tooltip Plotly natif des traces temporelles avec
  `hoverinfo: "none"`, pas `hoverinfo: "skip"`.
- Garder `onHover={handleHover}` et le flux `onCursorPoint` inchanges.
- Ne pas appliquer ce changement aveuglement aux scatter plots: ils n'ont pas
  aujourd'hui le meme tooltip custom temporel.

Pourquoi ce levier:

- Le code montre que la mise a jour du curseur passe par `onHover`, pas par le
  contenu affiche du `hovertemplate`.
- `hoverinfo: "none"` est le levier Plotly attendu pour masquer le label natif
  tout en laissant les evenements hover utilisables. `skip` est a eviter car il
  peut exclure les points du hover et donc casser `plotly_hover`.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/MetaSoftChart.tsx`
  - calcul `cursorAnnotations`
  - construction des traces temporelles dans `data`
  - `handleHover` doit rester branche sans changement de logique
- `local_ui/src/lib/metasoftChartHelpers.ts`
  - `buildCursorAnnotations`, seulement si un ajustement d'affichage est
    necessaire; le plan cible est de le re-utiliser tel quel.

Invariant a preserver:

- Hover sur un graphe temporel continue de mettre a jour le rail curseur,
  les annotations synchronisees et `Valeurs au curseur`.
- Aucune transformation de donnees, unite, lissage ou fallback metier.

Critere d'acceptation testable:

- Sur le graphe survole, il n'y a plus de tooltip Plotly blanc/default ni
  double source d'information.
- Le tooltip visible a le meme look que les graphes synchronises.
- En hover, les autres graphes et le rail curseur continuent de suivre le meme
  timestamp.

Risque:

- Moyen sans experimentation navigateur. Il faut confirmer dans Safari/local
  que `hoverinfo: "none"` conserve bien `onHover` avec la version Plotly du
  projet. Si ce n'est pas le cas, fallback minimal: garder les evenements et
  harmoniser `hoverlabel`/`hovertemplate` natifs au lieu de neutraliser le natif.

### 3. Repetition `Vitesse`: une seule source d'affichage

Decision technique exacte:

- Garder `Vitesse` dans `buildCursorAnnotations`, car c'est deja le tooltip
  custom commun.
- Retirer `Vitesse %{text}` du `hovertemplate` des traces temporelles dans
  `MetaSoftChart.tsx`, ou supprimer ce `hovertemplate` pour ces traces si
  `hoverinfo: "none"` est applique.
- Ne pas dupliquer une deuxieme ligne vitesse dans le template Plotly source.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/MetaSoftChart.tsx`
  - `speedHoverText`
  - `hovertemplate` des traces temporelles
- `local_ui/src/lib/metasoftChartHelpers.ts`
  - `buildCursorAnnotations` reste la source d'affichage de la vitesse.

Invariant a preserver:

- La valeur de vitesse reste issue de `point.values.speed_kmh`.
- Format francais et unite `km/h` conserves dans le tooltip custom.

Critere d'acceptation testable:

- En hover temporel, `Vitesse` apparait une seule fois.
- Les series physiologiques restent lisibles avec leurs unites.

Risque:

- Faible si le retrait est limite aux traces temporelles. Risque a eviter:
  supprimer par erreur une info utile des scatter plots qui n'ont pas encore
  d'annotation custom equivalente.

### 4. Tooltip EC: contraste et contenu lisible

Decision technique exacte:

- Ajouter `hoverlabel` sombre directement dans le `layout` de
  `ManualEconomyPlot`.
- Ajouter un `hovertemplate` explicite dans la factory locale `trace(...)` pour
  eviter le tooltip Plotly blanc et les valeurs brutes peu lisibles.
- Passer un `customdata` formate avec `secondsToClock` pour afficher le temps,
  sans modifier `x` ni les donnees de calcul.
- Garder les series et axes actuels; ne pas toucher a `manualSelections`,
  `manualArtifacts`, `metricsByStep` ou aux calculs EC.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/RunningEconomyManualSection.tsx`
  - `ManualEconomyPlot`
  - helper local `trace(...)`
  - `layout.hoverlabel`

Invariant a preserver:

- Les traces `VO2 brut`, `VO2 hors artefacts`, `VCO2 hors artefacts`,
  `VE hors artefacts` conservent les memes donnees et les memes couleurs.
- Les sliders, artefacts et table EC continuent d'utiliser les memes valeurs.

Critere d'acceptation testable:

- Le tooltip du graphe EC est sombre, contraste avec le fond, lisible sur la
  zone selectionnee et sur les zones d'artefact.
- Le tooltip affiche au minimum: nom de serie, temps formate, valeur numerique.

Risque:

- Moyen sur le wording/unite: VO2/VCO2 et VE sont en `L/min`, mais le tooltip ne
  doit pas inventer une precision ou une unite absente. Si le helper ne peut pas
  porter l'unite proprement en diff minimal, afficher la valeur numerique sans
  unite plutot que d'ajouter une unite douteuse.

### 5. Popover seuil: layout compact, lisible, sans overflow

Decision technique exacte:

- Elargir la popover a `width: min(420px, calc(100vw - 32px))`.
- Remplacer la grille de mode `2 colonnes` par `repeat(3, minmax(0, 1fr))`
  pour afficher `Ligne`, `Range`, `Precedent` sur une seule ligne.
- Garder les boutons marqueurs dans une grille lisible, avec largeur minimale
  permettant `VO2max` sans sortir de sa case.
- Remplacer le texte `x` par l'icone lucide `X` deja disponible dans
  `MetaSoftChart.tsx`.
- Mettre a jour le clamp de position de la popover pour ne pas conserver le
  magic number base sur l'ancienne largeur `240px`.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/MetaSoftChart.tsx`
  - `openMarkerProposal`
  - markup `.marker-popover`
  - bouton close de la popover
- `local_ui/src/styles.css`
  - `.marker-popover`
  - `.popover-head`
  - `.segmented`
  - `.marker-choice-grid`
  - `.marker-choice-grid button`

Invariant a preserver:

- Les modes `point`, `range`, `previous` gardent leur mapping exact.
- Les marqueurs `SV1`, `SV2`, `VO2_max`, `VMA` gardent leur valeur metier et
  leur couleur.
- Le click/drag continue de proposer un seuil au timestamp courant.

Critere d'acceptation testable:

- Les trois modes tiennent sur une ligne.
- `VO2max` ne deborde plus de son bouton.
- La popover reste dans le viewport du graphe, y compris proche du bord droit.
- La fermeture par icone ne change pas le marker courant.

Risque:

- Moyen: le clamp actuel utilise des dimensions implicites. Si la largeur CSS
  change sans mise a jour du clamp, la popover peut sortir du graphe. Le fix doit
  traiter les deux ensemble.

### 6. Artefact EC: bouton pour terminer et replier l'editeur

Decision technique exacte:

- Ajouter un bouton secondaire `Terminer` dans `ArtifactSliders`.
- Passer un callback `onDone` depuis `RunningEconomyManualSection` qui execute
  uniquement `setActiveExclusionIndex(null)`.
- Ne pas modifier `handlePlotClick`, `normalizeExclusions`, les bornes de
  selection, ni les calculs EC.
- Preferer le libelle `Terminer` a `Valider` pour ne pas faire croire a une
  sauvegarde persistante; l'artefact est deja applique par les sliders et le
  report reste le point de persistance.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/RunningEconomyManualSection.tsx`
  - state `activeExclusionIndex`
  - rendu `ArtifactSliders`
  - props de `ArtifactSliders`
  - header/actions de `ArtifactSliders`
- `local_ui/src/styles.css`
  - classes existantes de boutons/actions si necessaire, sans nouveau systeme.

Invariant a preserver:

- Creer un artefact continue de passer par `excludeMode` puis `handlePlotClick`.
- Les sliders restent live et recalculent la table exactement comme avant.
- `Supprimer` garde son comportement actuel.

Critere d'acceptation testable:

- Apres creation ou ajustement d'un artefact, cliquer `Terminer` replie
  l'editeur.
- Le chip `Artefact 1: ...` reste visible et permet de rouvrir l'editeur.
- Les valeurs de la table EC ne changent pas au clic `Terminer`.

Risque:

- Faible. Risque UX: `Terminer` peut etre lu comme une validation definitive.
  Le libelle et le style doivent rester secondaires par rapport a `Supprimer`.

### Checks a prevoir apres GO implementation

- Lecture ciblee du diff: verifier qu'aucun fichier backend, calcul, export ou
  payload report n'est touche.
- Build cible: `npm run build` dans `local_ui/`.
- Verification manuelle Safari:
  - hover graphe temporel source et graphe synchronise;
  - hover EC sur zone sombre/selection/artefact;
  - ouverture popover seuil proche bord droit;
  - `VO2max` dans son bouton;
  - creation puis `Terminer` sur artefact;
  - nav sans `Analyse`, section report toujours accessible.

### Lot 2 - Securiser les interactions

1. Rendre les modes de seuil et artefact explicites.
2. Ajouter garde-fou ou undo pour suppression de marqueur.
3. Renommer les statuts techniques.
4. Ajouter focus visible.

### Lot 3 - Rehierarchiser la lecture

1. Passer d'une grille de tous les graphes a une lecture principale.
2. Garder la grille complete comme secondaire/repliable si necessaire.
3. Mieux placer rail curseur, warnings, marqueurs et EC.

### Lot 4 - Durcissement produit

1. Resume avant report profil.
2. Fullscreen accessible.
3. Table marqueurs et table EC plus decisionnelles.
4. Direction visuelle Enduraw plus nette.

## Fichiers probablement touches

Pour le lot 1:

- `local_ui/src/App.tsx`
- `local_ui/src/components/MetaSoftChart.tsx`
- `local_ui/src/components/RunningEconomyManualSection.tsx`
- `local_ui/src/lib/metasoftChartHelpers.ts`
- `local_ui/src/styles.css`

Pour lots suivants:

- `local_ui/src/components/MarkerPanel.tsx`
- `local_ui/src/components/CursorRail.tsx`
- `local_ui/src/components/AnalysisExportSection.tsx`
- les fichiers du lot 1 selon besoin.

## Checks recommandes apres implementation

- `npm run build` dans `local_ui/`.
- Verification Safari locale sur:
  - tooltip graphe hovere;
  - tooltip graphe synchronise;
  - tooltip EC;
  - popup placement seuil;
  - `VO2max` dans bouton;
  - vitesse affichee une seule fois;
  - ajout artefact puis repli;
  - nav sans `Analyse`;
  - report profil visible mais payload non modifie;
  - focus clavier minimal.

## Hors scope tant que non demande

- Recalcul MetaSoft.
- Export JSON/audit.
- Modification endpoints locaux.
- Stockage session/profil.
- BDD/Mongo.
- Packaging.
- Nouvelle dependance UI.
- Refonte totale du shell Python.
