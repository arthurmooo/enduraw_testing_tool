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

## Plan d'execution Lot 2 - GO candidate

Scope strict: securiser les interactions existantes sans changer les gestes,
les calculs, le payload report, ni les etats internes. Pas de nouveau workflow
lourd, pas de dependance, pas de design system parallele.

### 1. Modes seuil et artefact explicites

Decision technique exacte:

- Seuils: conserver les gestes existants sur `MetaSoftChart`:
  click simple temporise pour ouvrir la popover, drag pour deplacer, clic droit
  pour supprimer. Ajouter uniquement du texte d'aide court dans la popover:
  mode `Ligne` = seuil a l'instant, `Range` = fenetre centree, `Precedent` =
  fenetre avant l'instant.
- Seuils: garder `markerModeLabel` tel quel pour ne pas toucher au contrat
  `MarkerMode`; ajouter un sous-label visuel sous les boutons de mode ou une
  ligne d'aide qui change avec `proposal.mode`.
- Artefacts: conserver `excludeMode` et `handlePlotClick`. Rendre l'etat actif
  explicite par:
  - `aria-pressed={excludeMode}` sur le bouton `Exclure artefact`;
  - libelle ou microcopy conditionnelle pres du bouton: actif = "Cliquez dans le
    graphe pour placer l'artefact", inactif = pas de texte additionnel ou texte
    neutre court;
  - ne pas transformer l'outil en modal ni ajouter validation supplementaire.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/MetaSoftChart.tsx`
  - popover `proposal`
  - rendu `.segmented`
  - event handlers existants inchanges: `openMarkerProposal`,
    `placeProposalMarker`, `handleMouseDown`, `handleContextMenu`
- `local_ui/src/components/RunningEconomyManualSection.tsx`
  - bouton `Exclure artefact`
  - state `excludeMode`
- `local_ui/src/styles.css`
  - classes existantes `.marker-popover`, `.segmented`, `.ec-actions`,
    eventuelle classe locale d'aide si necessaire

Invariant a preserver:

- Les valeurs internes `point`, `range`, `previous` restent identiques.
- Le drag des marqueurs, le click de placement et le clic droit existant restent
  disponibles.
- `excludeMode` continue seulement d'armer `handlePlotClick`; les calculs EC
  restent portes par les drafts/exclusions existants.

Critere d'acceptation testable:

- En ouvrant la popover seuil, l'utilisateur voit clairement ce que fait chaque
  mode sans deviner.
- Quand `Exclure artefact` est actif, l'UI indique explicitement que le prochain
  click dans le graphe cree un artefact.
- Les gestures actuels fonctionnent toujours: placement seuil, drag marqueur,
  clic droit suppression, click graphe artefact.

Risque:

- Faible si limite a du texte et `aria-pressed`.
- Risque UX: trop de microcopy dans une popover deja compacte. Garder une seule
  ligne contextuelle plutot qu'un bloc explicatif.

### 2. Suppression marqueur: garde-fou minimal

Decision technique exacte:

- Ajouter une confirmation native dans `handleContextMenu` avant
  `onDeleteMarker(target.marker)`.
- Message cible: `Supprimer le marqueur SV1 ?` avec format `VO2max` pour
  `VO2_max`.
- Ne pas ajouter de snackbar/undo state pour ce lot: l'undo demanderait de
  stocker l'ancien `DraftMarker`, d'ajouter une action de restauration et de
  gerer l'expiration. C'est plus de state fragile pour un geste deja rare et
  cache.
- Ne pas modifier `deleteMarker` dans `App.tsx`, qui reste le point unique de
  mutation du draft et du dirty state.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/MetaSoftChart.tsx`
  - `handleContextMenu`
- Optionnel si duplication de label evitee:
  - helper local tres court `markerDisplayName(marker)` dans le meme fichier,
    ou expression inline deja utilisee ailleurs.

Invariant a preserver:

- `onDeleteMarker` appelle toujours `deleteMarker`.
- `deleteMarker` continue de remettre le marqueur a `t_seconds: null` via
  `buildDraftMarker(..., null, "point")` et de marquer dirty.
- Aucun changement de serialization, report ou payload.

Critere d'acceptation testable:

- Clic droit sur un marqueur affiche une confirmation.
- `Annuler` ne change pas le tableau Marqueurs.
- `OK` supprime le marqueur comme aujourd'hui et le statut passe a sauvegarder.

Risque:

- Moyen-faible: `window.confirm` est visuellement natif et moins elegant, mais
  c'est le garde-fou le plus court et le moins fragile.
- Arbitrage Arthur possible: si le produit refuse le confirm navigateur, il faut
  planifier un mini-popover de confirmation ou un undo toast, ce qui est un
  scope plus large que Lot 2 minimal.

### 3. Statuts techniques: labels utilisateurs uniquement

Decision technique exacte:

- Ne pas renommer les etats internes ni les valeurs metier.
- Mapper uniquement les labels affiches:
  - `preview` -> `Brouillon`
  - `needsSave` -> `A reporter`
  - `Python` -> `Officiel`
  - `Report` -> `Report en cours`
  - `Overwrite` -> `Ecrasement en cours`
- Appliquer le mapping localement:
  - `MarkerPanel` pour les statuts de marqueurs;
  - `AnalysisExportSection` pour le badge `busy`;
  - eventuellement header `Analyse Python` vers `Analyse locale OK` seulement si
    le lead veut harmoniser le libelle de badge, sans changer la logique.
- Garder les classes visuelles existantes `status-muted`, `status-warn`,
  `status-ok`.

Fichiers et fonctions/classes touches:

- `local_ui/src/components/MarkerPanel.tsx`
  - rendu de la colonne `Statut`
  - note sous tableau
- `local_ui/src/components/AnalysisExportSection.tsx`
  - affichage de `busy`
- Optionnel:
  - `local_ui/src/App.tsx` uniquement si le badge header `Analyse Python` doit
    etre renomme aussi

Invariant a preserver:

- `dirtyMarkers`, `confirmedMarkers`, `busy`, `runOfficialAction("Report")` et
  `runOfficialAction("Overwrite")` restent inchanges.
- Aucun changement de payload ou de detection de conflit.
- Les couleurs de statut restent coherentes: brouillon neutre, a reporter warn,
  officiel ok.

Critere d'acceptation testable:

- Le tableau marqueurs n'affiche plus `preview`, `needsSave` ni `Python`.
- Pendant un report, le badge n'affiche plus `Report` ou `Overwrite` brut.
- Aucun test fonctionnel de report ne change de payload.

Risque:

- Faible. Risque principal: choisir un label qui implique une persistance
  excessive. `A reporter` est preferable a `Non sauvegarde` car la sauvegarde
  reelle passe par le report profil.

### 4. Focus visible clavier

Decision technique exacte:

- Ajouter un style CSS `:focus-visible` commun pour les controles interactifs:
  boutons, inputs, toggles et boutons de table.
- Ne pas supprimer le `outline: none` existant sur `.field input`; le compenser
  avec une regle plus specifique `.field input:focus-visible`.
- Utiliser les couleurs existantes Enduraw:
  `outline: 2px solid rgba(16, 211, 143, 0.78)` et
  `outline-offset: 2px`.
- Ne pas introduire de composant focus, hook clavier ou dependance.

Fichiers et fonctions/classes touches:

- `local_ui/src/styles.css`
  - regle globale `button:focus-visible, input:focus-visible`
  - regles ciblees si necessaire pour `.table-icon-button`,
    `.series-toggle`, `.nav-toggle`, `.marker-choice-grid button`,
    `.segmented button`

Invariant a preserver:

- Les styles hover/active existants restent identiques.
- Les inputs range gardent leur rendu actuel.
- Aucun changement de navigation clavier fonctionnelle hors affichage du focus.

Critere d'acceptation testable:

- En tab clavier, le focus est visible sur nav, filtres, toggles series, boutons
  popover, boutons EC, table EC et report.
- Le focus ne deforme pas les boutons et ne provoque pas d'overflow.
- Le focus reste visible sur fond sombre et sur panels.

Risque:

- Faible. Risque a surveiller: outline coupe par containers avec overflow,
  notamment dans `.table-wrap` ou `.stage-strip`; `outline-offset: 2px` limite
  le probleme sans changer les layouts.

### Checks a prevoir apres GO implementation

- `npm --prefix local_ui run build`.
- `git diff --check`.
- Verification Safari manuelle:
  - popover seuil et changement des trois modes;
  - clic droit suppression marqueur: annuler puis confirmer;
  - mode artefact actif/inactif;
  - libelles de statuts marqueurs et report;
  - navigation clavier Tab/Shift+Tab sur controles visibles.

## Plan d'execution Lot 3 - GO candidate

Objectif: rehierarchiser la lecture MetaSoft locale pour reduire la lourdeur
percue sans perdre les graphes, les gestes et les controles existants.

### Etat actuel

- `local_ui/src/App.tsx` derive `READING_GRAPH_CONFIGS` depuis
  `GRAPH_CONFIGS.filter((graph) => graph.source === "points")`, puis monte tous
  les graphes de lecture dans `.charts-grid`.
- Chaque graphe est rendu avec le meme poids visuel via `MetaSoftChart`, avec
  toggles series, plein ecran, zoom, double-clic reset, marqueurs, tooltip
  synchronise, filtres phase, lissage et paliers vitesse.
- Les etats de synchronisation importants vivent deja dans `App.tsx`:
  `timeXRange`, `timeResetRevision`, `cursorPoint`, `cursorSourceGraphId`,
  `phaseFilter`, `smoothingSeconds`, `showSpeedBands`.
- `CursorRail` contient `Valeurs au curseur` et `Warnings` en colonne droite de
  la grille de lecture.
- `MarkerPanel`, `RunningEconomyManualSection` et `AnalysisExportSection` sont
  empiles apres la lecture. EC possede deja son propre workbench et ne doit pas
  etre melange a la lecture brute.
- `MetaSoftChart` fixe aujourd'hui une hauteur compacte pour les cartes
  standard (`body(260)`) et une hauteur adaptee en plein ecran.

### Probleme UX racine

- La page donne le meme rang a tous les graphes, alors que l'utilisateur doit
  d'abord lire une courbe principale, puis comparer ou verifier les graphes
  secondaires.
- Le nombre de Plotly visibles simultanement cree une charge mentale et
  graphique elevee: axes doubles, phases, paliers, marqueurs et tooltips
  s'accumulent partout.
- Les panneaux utiles (`Valeurs au curseur`, `Warnings`, `Marqueurs`, `EC`,
  `Report`) sont presents, mais l'ordre ne raconte pas assez le workflow:
  lire, poser/verifier les marqueurs, analyser EC, reporter.
- La root cause n'est pas un probleme de style ou de donnees: c'est
  l'orchestration des composants existants dans `App.tsx`.

### Plan d'implementation precis

#### 1. Lecture principale avec graphe focus

Decision technique exacte:

- Ajouter dans `App.tsx` un etat UI local `selectedReadingGraphId`.
- Deriver `selectedReadingGraph` depuis `READING_GRAPH_CONFIGS`, avec fallback
  sur un graphe stable si l'id n'existe plus.
- Choisir par defaut `vo2_vco2_time` si disponible, sinon le premier graphe de
  `READING_GRAPH_CONFIGS`.
- Rendre un seul `MetaSoftChart` principal dans une zone `.reading-focus`.
- Passer a ce graphe les memes props que les cartes actuelles pour conserver
  toutes les interactions existantes.
- Ajouter a `MetaSoftChart` une prop optionnelle `height?: number` avec valeur
  par defaut `260`, utilisee uniquement pour la vue carte normale. Le plein
  ecran garde son calcul actuel.

Fichiers/fonctions/classes probables:

- `local_ui/src/App.tsx`
  - etat `selectedReadingGraphId`
  - derive `selectedReadingGraph`
  - rendu de la zone focus
- `local_ui/src/components/MetaSoftChart.tsx`
  - prop optionnelle `height`
  - appel `body(height)` au lieu de `body(260)`
- `local_ui/src/styles.css`
  - `.reading-workspace`
  - `.reading-focus`
  - hauteur/respiration du graphe principal

Invariant a preserver:

- Aucun changement de `GRAPH_CONFIGS`, des series, des calculs, des donnees ou
  des payloads.
- Zoom temporel synchronise conserve via `timeXRange`.
- Double-clic reset conserve via `timeResetRevision`.
- Marqueurs et plein ecran continuent de passer par `MetaSoftChart`.

Critere d'acceptation testable:

- A l'ouverture de la page, un graphe principal plus lisible est visible.
- Les toggles series, le plein ecran, le hover synchronise, les marqueurs, le
  zoom et le reset fonctionnent sur ce graphe principal comme avant.
- Changer filtre phase, lissage ou paliers vitesse impacte le graphe principal.

Risque:

- Faible a moyen. `hiddenSeries` est local a chaque `MetaSoftChart`; si un
  utilisateur change de graphe focus puis revient, l'etat des toggles peut etre
  reinitialise. Preserver cet etat par graphe ajouterait du state transverse et
  n'est pas justifie pour Lot 3 sauf demande explicite.

#### 2. Selection de graphe sans mini Plotly

Decision technique exacte:

- Ajouter sous ou a cote du graphe principal un selecteur de graphes base sur
  `READING_GRAPH_CONFIGS`.
- Utiliser des boutons/list items natifs du style existant, pas de vignettes
  Plotly et pas de nouvelle abstraction.
- Afficher le titre du graphe et un indicateur discret du type `Temps` ou
  `Relation` derive de `graph.kind`.
- Le clic met a jour `selectedReadingGraphId`.

Fichiers/fonctions/classes probables:

- `local_ui/src/App.tsx`
  - rendu du selecteur
- `local_ui/src/styles.css`
  - `.graph-picker`
  - `.graph-picker-button`
  - etat actif/focus

Invariant a preserver:

- Tous les graphes restent disponibles.
- Le selecteur ne remplace pas les toggles series internes au graphe.
- Aucun mapping metier supplementaire des variables.

Critere d'acceptation testable:

- Chaque graphe de `READING_GRAPH_CONFIGS` est selectionnable.
- Selectionner un graphe scatter conserve ses interactions propres.
- Le selecteur est utilisable clavier avec focus visible Lot 2.

Risque:

- Faible. Le principal arbitrage non bloquant est le libelle court des graphes:
  il faut reutiliser `graph.title` pour eviter un deuxieme dictionnaire.

#### 3. Grille complete secondaire visible

Decision technique exacte:

- Garder une section secondaire visible directement avec tous les graphes de
  lecture sauf le graphe deja affiche en focus.
- Ne pas ajouter de collapse par defaut: la comparaison simultanee est une
  contrainte produit.
- Rendre la grille existante avec les memes props, en excluant le graphe deja
  affiche en focus pour eviter un double rendu inutile.
- Conserver les classes de grille existantes autant que possible.

Fichiers/fonctions/classes probables:

- `local_ui/src/App.tsx`
  - rendu permanent de la grille secondaire
- `local_ui/src/styles.css`
  - `.view-mode-toggle`
  - `.reading-workspace`
  - ajustements mineurs de `.charts-grid` si necessaire

Invariant a preserver:

- Les graphes secondaires gardent les memes interactions lorsqu'ils sont
  ouverts.
- La synchronisation globale continue de passer par les props existantes.
- Pas de rendu miniature approximatif ni de degradation de precision.

Critere d'acceptation testable:

- Par defaut, le graphe focus et tous les autres graphes de lecture sont
  visibles.
- Les graphes secondaires affichent zoom, hover, marqueurs, plein ecran et
  toggles.
- Changer le graphe focus garde tous les graphes visibles sans doublonner le
  graphe focus.

Risque:

- Moyen. Le cout Plotly redevient celui d'une vue simultanee, mais c'est le
  comportement produit demande. La compensation reste l'absence de double rendu
  du graphe focus dans la grille secondaire.

#### 4. Repositionner `Valeurs au curseur` et `Warnings`

Decision technique exacte:

- Garder `CursorRail` comme composant unique pour eviter une duplication de
  logique d'affichage.
- Le placer dans la nouvelle `.reading-workspace`, a droite du graphe principal
  sur desktop et sous le graphe sur mobile.
- Ne pas modifier la liste `CURSOR_VALUES` ni la selection des warnings.
- Option CSS seulement: rendre le rail plus compact si le graphe principal
  prend plus de place.

Fichiers/fonctions/classes probables:

- `local_ui/src/App.tsx`
  - deplacement du rendu `CursorRail`
- `local_ui/src/components/CursorRail.tsx`
  - idealement aucun changement
- `local_ui/src/styles.css`
  - `.reading-workspace`
  - `.side-rail` responsive si necessaire

Invariant a preserver:

- Les valeurs au curseur restent issues de `analysis` et `cursorPoint`.
- Les warnings restent informatifs, sans changer leur source ni leur nombre.
- Aucun calcul ou fallback de donnees n'est modifie.

Critere d'acceptation testable:

- En hover sur le graphe principal, `Valeurs au curseur` se met a jour.
- Les warnings restent visibles dans le contexte de lecture.
- Sur mobile/tablette, le rail ne compresse pas le graphe principal.

Risque:

- Faible. Le risque principal est purement layout: colonne trop etroite sur
  largeurs intermediaires. A couvrir par CSS responsive.

#### 5. Reordonner Marqueurs, EC et Report sans les melanger

Decision technique exacte:

- Conserver les ancres existantes: `metasoft-reading`, `metasoft-markers`,
  `metasoft-ec`, `metasoft-profile-report`.
- Apres la lecture, afficher une zone workflow plus claire:
  `MarkerPanel` comme etape de validation des seuils et `AnalysisExportSection`
  comme action de report.
- Sur desktop, placer `MarkerPanel` et `AnalysisExportSection` dans une grille
  sobre si cela reduit la longueur sans tasser la table; sur mobile, empiler.
- Garder `RunningEconomyManualSection` comme section dediee `EC`, separee de la
  lecture brute et de la grille des graphes.
- Ne pas deplacer le graphe EC dans le focus de lecture.

Fichiers/fonctions/classes probables:

- `local_ui/src/App.tsx`
  - structure d'ordre des sections
  - eventuel wrapper `.workflow-grid`
- `local_ui/src/components/MarkerPanel.tsx`
  - idealement aucun changement
- `local_ui/src/components/AnalysisExportSection.tsx`
  - idealement aucun changement
- `local_ui/src/components/RunningEconomyManualSection.tsx`
  - aucun changement de logique
- `local_ui/src/styles.css`
  - `.workflow-grid`
  - responsive pour la table marqueurs et le report

Invariant a preserver:

- Les marqueurs restent officialises par le flux Python/report existant.
- Le report profil conserve ses callbacks et son payload.
- EC reste une analyse manuelle dediee, sans changement de calcul ni de
  sauvegarde.

Critere d'acceptation testable:

- Les liens de nav `Marqueurs`, `EC`, `Report` scrollent toujours vers les bons
  contenus.
- La table marqueurs reste lisible et utilisable.
- Le report reste accessible sans traverser toute la grille de graphes.
- L'onglet/zone EC reste separe et identifiable comme analyse, pas lecture
  brute.

Risque:

- Moyen. Mettre report et marqueurs cote a cote peut compresser la table sur
  certaines largeurs. Si la table devient trop dense, fallback: garder
  `MarkerPanel` pleine largeur et placer `Report` juste apres, sans grille.

### Strategie performance

- Ne pas rendre deux fois le graphe focus.
- Ne pas creer de mini graphes Plotly: le selecteur est textuel.
- Reutiliser `MetaSoftChart` pour eviter une logique de plotting parallele.
- Accepter le cout de la vue simultanee: l'utilisateur l'a demande
  explicitement et les features restent completes.

### Strategie de test apres GO implementation

- `npm --prefix local_ui run build`.
- `git diff --check`.
- Verification Safari manuelle:
  - ouverture initiale: un graphe principal, rail curseur/warnings, graphes
    secondaires visibles;
  - selection de plusieurs graphes time et scatter;
  - zoom sur graphe principal: les graphes time montes respectent le range
    global;
  - double-clic reset depuis graphe principal et depuis grille secondaire;
  - hover synchronise entre graphes montes;
  - toggles series et plein ecran depuis graphe principal et secondaire;
  - placement/deplacement/suppression de marqueur;
  - filtres phase, lissage, paliers vitesse;
  - nav vers `Marqueurs`, `EC`, `Report`;
  - responsive desktop, largeur intermediaire et mobile.

### Points hors scope Lot 3

- Changement des calculs MetaSoft, EC, VO2, FC ou derives.
- Changement du backend Python, des exports, du stockage session, DB/Mongo ou
  payload report.
- Refonte visuelle globale, nouvelle DA, design system parallele ou nouvelle
  dependance.
- Refonte des tooltips Lot 1/2 deja traites.
- Resume avant report profil, table decisionnelle avancee et accessibilite
  fullscreen: a garder pour Lot 4.
- Persistance fine des toggles series par graphe si le composant est demonte:
  non necessaire pour ce lot.

### Verdict

GO candidate.

Justification: le lot peut etre implemente avec une orchestration minimale dans
`App.tsx`, une petite extension optionnelle de `MetaSoftChart` pour la hauteur,
et du CSS responsive. Les composants metier et data restent inchanges, EC reste
separe de la lecture brute, et la performance s'ameliore par defaut en montant
moins de Plotly. Aucun arbitrage bloquant n'est identifie; le choix du graphe
principal par defaut (`V'O2, V'CO2`) peut etre change sans impact
architectural si Arthur prefere une autre courbe.

### Note correction utilisateur apres Lot 4

- Decision finale utilisateur: deux modes de vue lecture.
- Mode `Tout` par defaut: tous les graphes de lecture sont visibles
  simultanement, sans graphe cache.
- Mode `Focus`: graphe principal + selecteur, pour travailler au calme sur un
  graphe.
- Le plein ecran reste disponible sur chaque graphe dans les deux modes.

## Plan d'execution Lot 4 - GO candidate

Objectif: durcir l'UI locale MetaSoft avant validation finale, sans changer les
calculs, les series, les unites, les callbacks metier, les exports ou les
payloads report.

### Etat actuel

- `App.tsx` orchestre le flux complet: lecture, marqueurs, EC et report. Le
  report appelle `serializeMarkerSelections(draftMarkers)` puis
  `manualEconomyRef.current?.reportPayload()` avant `apiPost`.
- `AnalysisExportSection` affiche seulement le bouton `Reporter au profil`, les
  conflits, l'erreur et le resultat. Il ne montre pas encore ce qui va etre
  officialise juste avant le clic.
- `MarkerPanel` montre deja les statuts utilisateurs `Brouillon`, `A reporter`
  et `Officiel`, mais la table reste principalement numerique: le statut ne
  pilote pas assez la lecture de decision.
- `RunningEconomyManualSection` possede l'etat EC courant, les lignes preview,
  les paliers inclus/ecartes et le handle `reportPayload()`. C'est la source
  correcte pour resumer l'EC sans recalculer ailleurs.
- `MetaSoftChart` a deja une modale fullscreen avec `role="dialog"`,
  `aria-modal="true"` et bouton de fermeture. Il manque encore le minimum
  clavier attendu: focus initial clair, fermeture par `Escape`, titre relie au
  dialog.
- Les fixes recents a preserver sont concentres dans `MetaSoftChart`,
  `metasoftChartHelpers`, `chartUtils`, `RunningEconomyManualSection` et
  `App.tsx`: zoom synchronise, double-click reset, fullscreen ouvert, tooltips
  custom/synchronises, paliers vitesse, arrondi FC, EC independante.

### Probleme UX racine

- La page sait calculer et reporter, mais elle ne donne pas assez de moment de
  verification juste avant l'action irreversible de report profil.
- Les etats importants existent, mais ils sont disperses: marqueurs dans une
  table, EC dans une autre, warnings dans le rail. Le bouton report arrive sans
  synthese de decision.
- Les tables sont exactes mais pas assez hierarchisees: un utilisateur doit
  scanner toutes les colonnes pour savoir quoi verifier, inclure ou reporter.
- Le fullscreen fonctionne, mais il reste un overlay technique plutot qu'un
  dialog produit accessible.
- La root cause n'est pas metier: c'est une couche de presentation et de
  confirmation manquante autour des donnees deja presentes.

### Plan d'implementation precis

#### 1. Resume avant report profil

Decision technique exacte:

- Ajouter un resume visible dans `AnalysisExportSection`, au-dessus du bouton
  `Reporter au profil`, sans bouton preview separe.
- Le resume doit afficher:
  - marqueurs qui seront reportes, avec nom, statut utilisateur, temps/fenetre
    et valeurs clefs deja affichees dans `MarkerPanel`;
  - EC manuelle: paliers inclus et ecartes, vitesse, bornes, EC si disponible;
  - warnings critiques: uniquement `warning.blocking === true`; afficher aussi
    le nombre de warnings non bloquants sans les presenter comme critiques.
- Ne pas appeler une API de preview et ne pas creer de nouveau payload.
- Pour l'EC, ne pas reconstruire le calcul dans `App.tsx` ou
  `AnalysisExportSection`. Faire remonter depuis `RunningEconomyManualSection`
  une synthese UI derivee des `rows` et `drafts` existants.
- Option d'implementation minimale:
  - ajouter un type exporte `ManualEconomyReportSummary` dans
    `RunningEconomyManualSection.tsx`;
  - ajouter une prop optionnelle `onReportSummaryChange`;
  - calculer la synthese via `useMemo` depuis `rows`, `drafts` et
    `stableStages`;
  - notifier `App.tsx` via `useEffect`;
  - passer cette synthese a `AnalysisExportSection`.
- Pour les marqueurs, construire dans `App.tsx` une synthese UI depuis
  `draftMarkers`, `confirmedMarkers`, `dirtyMarkers` et les helpers existants
  `MARKER_NAMES`, `secondsToClock`, `formatNumber`. Cette synthese n'est pas le
  payload; elle sert seulement a l'affichage.

Fichiers/fonctions/classes probables:

- `local_ui/src/App.tsx`
  - etat `manualEconomyReportSummary`
  - derive `markerReportSummary`
  - passage des summaries et warnings a `AnalysisExportSection`
- `local_ui/src/components/RunningEconomyManualSection.tsx`
  - type `ManualEconomyReportSummary`
  - prop `onReportSummaryChange?: (...) => void`
  - `useMemo` + `useEffect` de synthese UI
  - aucun changement de `buildReportPayload`
- `local_ui/src/components/AnalysisExportSection.tsx`
  - rendu `ReportSummary`
  - props de synthese
- `local_ui/src/styles.css`
  - `.report-summary`, `.summary-grid`, `.summary-list`, badges de niveau

Invariant a preserver:

- `reportProfile()` continue d'envoyer exactement:
  `marker_selections: serializeMarkerSelections(draftMarkers)` et
  `...(manualEconomyRef.current?.reportPayload() ?? {})`.
- Aucun changement de `manual_running_economy_selections`,
  `manual_running_economy_stage_selections`, `marker_selections` ou
  `conflict_policy`.
- Le resume ne devient jamais source de verite: il lit les etats existants.
- Les warnings critiques sont definis uniquement par `blocking === true`; ne
  pas inferer une criticite depuis le texte.

Critere d'acceptation testable:

- Avant le bouton report, l'utilisateur voit les 4 marqueurs et leur statut
  actuel.
- Les paliers EC inclus/ecartes visibles dans le resume correspondent au
  `Tableau EC`.
- Les warnings bloquants sont separes des warnings non bloquants; s'il n'y en a
  pas, le resume le dit explicitement.
- Modifier un marqueur ou inclure/ecarter un palier EC met a jour le resume
  sans clic preview.
- Le payload envoye au report reste identique a avant Lot 4 pour le meme etat
  UI.

Risque:

- Moyen. Le principal risque est de dupliquer de la logique d'affichage entre
  tables et resume. Le garder acceptable en limitant le resume aux champs deja
  visibles et en ne creant aucun helper generique "report builder".

#### 2. Fullscreen accessible sans casser Plotly

Decision technique exacte:

- Garder le fullscreen dans `MetaSoftChart`; ne pas creer de composant modal
  global.
- Ajouter un `id` stable au titre de la modale via `useId()` et relier le
  dialog avec `aria-labelledby`.
- Donner un label explicite au dialog, par exemple `Plein ecran - {graph.title}`.
- Quand `fullscreen` passe a `true`, focaliser le bouton fermer avec un ref.
- Ajouter un listener `keydown` actif uniquement en fullscreen pour fermer sur
  `Escape`.
- Ne pas fermer au clic backdrop pour eviter les fermetures involontaires
  pendant les interactions Plotly.
- Ne pas toucher aux handlers Plotly de zoom, relayout, double-click ou hover.

Fichiers/fonctions/classes probables:

- `local_ui/src/components/MetaSoftChart.tsx`
  - import `useId`
  - ref bouton fermer
  - `useEffect` focus + `Escape`
  - `aria-labelledby`
- `local_ui/src/styles.css`
  - polish `.modal-header`, `.modal-panel`, focus visible deja commun

Invariant a preserver:

- `fullscreenGraphId` reste l'etat unique dans `App.tsx`.
- Le placeholder de carte reste present quand la modale est ouverte.
- Zoom, double-click reset, tooltips, paliers vitesse et marqueurs restent
  routes par `PointChartBody`.

Critere d'acceptation testable:

- Ouvrir fullscreen place le focus sur le bouton fermer.
- `Escape` ferme la modale.
- Tab permet d'atteindre les toggles series et le bouton fermer avec focus
  visible.
- Zoom, reset double-clic, hover synchronise et plein ecran restent fonctionnels
  apres ouverture/fermeture.

Risque:

- Faible a moyen. Un focus trap complet serait plus lourd et plus risque avec
  Plotly; pour Lot 4, focus initial + Escape + labels ARIA couvrent le minimum
  utile sans perturber les interactions graphe.

#### 3. Tables marqueurs et EC plus decisionnelles

Decision technique exacte:

- `MarkerPanel`:
  - ajouter des classes de ligne selon statut: officiel, a reporter,
    brouillon;
  - ajouter une petite synthese en tete: nombre de marqueurs `Officiel`,
    `A reporter`, `Brouillon`;
  - conserver les valeurs et colonnes actuelles;
  - ne pas changer `currentVo2maxMlKgMin` ni `percentVo2Max`.
- `RunningEconomyManualSection`:
  - ajouter une synthese en tete du `Tableau EC`: nombre de paliers inclus et
    ecartes;
  - rendre `Inclus` / `Ecarte` plus lisible par classes dediees, sans changer
    le bouton qui toggle `draft.enabled`;
  - ajouter `aria-pressed={draft.enabled}` sur le bouton inclus/ecarte;
  - renforcer visuellement la ligne selectionnee et les lignes ecartees via CSS
    existant ou classes dediees.

Fichiers/fonctions/classes probables:

- `local_ui/src/components/MarkerPanel.tsx`
  - derive de compteurs statut
  - classes de ligne
- `local_ui/src/components/RunningEconomyManualSection.tsx`
  - derive compteurs inclus/ecartes
  - `aria-pressed`
  - classes de ligne/bouton si necessaire
- `local_ui/src/styles.css`
  - `.table-summary`
  - `.marker-row-official`, `.marker-row-dirty`, `.marker-row-draft`
  - `.ec-row-included`, `.ec-row-excluded`
  - badges inclus/ecarte

Invariant a preserver:

- Aucun changement de valeurs, arrondis, colonnes de donnees, calcul EC ou
  selection de points.
- Un clic sur une ligne EC continue de selectionner le palier.
- Un clic sur le bouton inclus/ecarte continue uniquement de toggler
  `draft.enabled`.

Critere d'acceptation testable:

- La table marqueurs permet de distinguer immediatement officiel, brouillon et
  a reporter.
- La table EC permet de distinguer immediatement inclus et ecarte.
- Les chiffres affiches sont identiques a avant Lot 4 pour le meme fichier.
- Les interactions table EC restent identiques.

Risque:

- Faible. Risque principal: sur-colorer les tables et nuire a la lecture des
  nombres. Garder des fonds faibles et des bordures/status pills plutot que de
  grands aplats.

#### 4. Direction visuelle Enduraw plus nette, sans refonte

Decision technique exacte:

- Rester dans les couleurs actuelles: fond sombre, vert Enduraw pour action
  positive, orange pour attention, rouge uniquement risque/conflit.
- Renforcer la hierarchie par:
  - titres de sections plus nets;
  - spacing coherent entre section, panel et table;
  - badges de statut reutilisant `.status-*`;
  - bordures actives sobres sur lignes/paliers importants.
- Ne pas ajouter de hero, illustration, gradient decoratif, cartes imbriquees,
  design system, tokens globaux massifs ou nouvelle dependance.
- Si du CSS commun est ajoute, le limiter a des classes de presentation
  concretes reutilisees par ce lot.

Fichiers/fonctions/classes probables:

- `local_ui/src/styles.css`
  - petites classes de hierarchie et decision
- Eventuellement `AnalysisExportSection.tsx`, `MarkerPanel.tsx`,
  `RunningEconomyManualSection.tsx` pour appliquer les classes.

Invariant a preserver:

- La DA reste celle de l'UI locale actuelle.
- Pas de changement structurel de navigation Lot 3.
- Pas de carte dans carte: le resume report vit dans le panel report existant,
  avec blocs internes plats.

Critere d'acceptation testable:

- La page reste sobre et operationnelle, pas marketing.
- Les etats principaux se lisent avant les details numeriques.
- Aucun texte ne deborde sur desktop, largeur intermediaire ou mobile.

Risque:

- Faible. Le risque est de refaire le style au lieu de durcir le produit; le GO
  implementation doit rester limite aux zones report, tables et fullscreen.

### Strategie pour preserver les fixes recents

- Ne pas toucher a `chartUtils.ts` ni aux helpers de zoom sauf bug bloquant
  decouvert.
- Ne pas modifier `buildCursorAnnotations`, les hovertemplates time/scatter ou
  `hoverinfo: "none"` des time charts.
- Ne pas changer `handleTimeXRangeChange`, `timeRangeKey`,
  `timeZoomResetRevision` ou les guards de reset.
- Ne pas modifier la logique des paliers vitesse ni les couleurs/taille deja
  validees.
- Ne pas changer `formatNumber` ni l'arrondi FC.
- Ne pas deplacer l'EC dans la lecture; seulement resumer son etat avant report.

### Strategie de test apres GO implementation

- `npm --prefix local_ui run build`.
- `git diff --check`.
- Verification Safari manuelle:
  - resume report avant clic, avec marqueurs, EC inclus/ecartes et warnings;
  - modification d'un marqueur puis resume qui passe `A reporter`;
  - toggle EC `Inclus` / `Ecarte` puis resume mis a jour;
  - report profil: payload et comportement inchanges, conflits toujours
    affiches;
  - fullscreen: ouverture, focus fermer, `Escape`, toggles series, zoom,
    double-click reset, hover;
  - tables marqueurs et EC lisibles sur desktop, largeur intermediaire et
    mobile;
  - regression Lot 1/2/3: tooltips uniques, vitesse non dupliquee, tooltip EC
    lisible, artefact `Terminer`, vue simultanee des graphes ouverte par
    defaut.

### Points hors scope Lot 4

- Backend Python, endpoints, BDD/Mongo, stockage session.
- API preview separee ou nouveau bouton preview.
- Changement des calculs MetaSoft, EC, VO2, FC, RER, DE ou derives.
- Changement des payloads report, serialization JSON, noms de champs ou
  conflict policy.
- Refonte graphique globale, nouvelle navigation, nouveau design system,
  nouvelle dependance.
- Focus trap modal complet si le minimum clavier fonctionne; a reevaluer plus
  tard seulement si usage clavier strict requis.

### Verdict

GO candidate.

Justification: le lot est faisable en frontend uniquement, avec une synthese
UI lue depuis les etats deja proprietaires (`draftMarkers` dans `App.tsx`, EC
dans `RunningEconomyManualSection`) et sans toucher aux chemins de calcul ou de
payload. Le seul point d'attention est la remontee de la synthese EC: elle doit
rester une vue derivee, pas une deuxieme source de verite.

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
