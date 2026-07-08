# MetaSoft local - plan optimisation performance

Date: 2026-07-08
Branche: `feature/metasoft-react-local-ui`
Scope: app locale Python + UI React MetaSoft.

## Objectif

Rendre la visualisation MetaSoft locale fluide sur machines modestes sans degrader:
- les 9 graphes alignes MetaSoft Studio;
- les paliers de vitesse en background;
- le lissage visuel;
- le zoom, fullscreen, clic/drag marqueurs;
- le report profil et l'export JSON/audit;
- la precision officielle des valeurs, qui reste cote Python sur points XML bruts.

## Garde-fous

- Aucun downsampling destructeur comme source de clic, marqueur, report ou export.
- Aucun lissage utilise dans les calculs officiels.
- Aucun retrait de graphe, palier, marqueur ou warning.
- Aucun changement BDD.
- Les donnees completes restent disponibles cote Python pour officialisation/export/audit.
- Le payload React peut etre allege si les champs retires ne sont pas lus par l'UI.

## Diagnostic retenu

### P0 - Rerenders globaux au hover

`App.tsx` stocke `cursorPoint` au niveau racine. Chaque hover Plotly appelle `setCursorPoint`, ce qui peut rerender toute la page et les 9 graphes, alors que seul le rail de valeurs doit changer.

Plan:
- rendre les callbacks stables avec `useCallback`;
- ignorer les hover identiques;
- throttler les updates curseur via `requestAnimationFrame`;
- memoizer `MetaSoftChart`.

Invariant: le curseur est purement visuel; aucun export/report ne lit ce state.

### P0 - Drag marqueur trop couteux

Le drag met a jour un state React a chaque mousemove, puis reconstruit les shapes Plotly. C'est couteux car Plotly relayout en boucle.

Plan:
- throttler le drag via `requestAnimationFrame`;
- eviter `setMarkerHover` si la cible n'a pas change;
- conserver le calcul exact en secondes depuis la position souris;
- ne changer le marqueur officiel qu'au mouseup.

Invariant: `onPlaceMarker` envoie les memes secondes/bornes a Python; officialisation toujours sur points bruts.

### P0 - Fullscreen double le rendu

Quand une modale fullscreen est ouverte, le graphe normal reste monte et un second Plotly est ajoute.

Plan:
- remplacer le corps de carte par un placeholder pendant le fullscreen, ou eviter de monter deux Plotly actifs.

Invariant: fullscreen conserve zoom, clic, drag, toggles serie.

### P1 - Payload UI trop lourd

`/analysis` renvoie `point.raw` et `point.value_sources` pour chaque point. Ces champs sont utiles cote Python/audit, mais pas pour l'UI React actuelle.

Plan:
- ajouter une fonction de payload UI cote serveur local qui retire `raw` et `value_sources` uniquement dans la reponse React;
- garder `context["analysis"]` complet en memoire pour officialisation, report, export JSON et sidecar audit;
- ajouter un test API qui verifie que le payload UI est slim et que `officialize` fonctionne encore.

Invariant: JSON Valentin, sidecar audit et marqueurs officiels inchanges.

### P1 - XML repars a chaque action

`_match_context` repars le XML a chaque endpoint. C'est acceptable pour un XML normal, mais inutile et perceptible sur gros XML.

Plan:
- cache memoire local par `match_id`, chemin XML, mtime, size et masse profil fallback;
- invalidation si la session active change ou si le fichier XML/profil mass change;
- aucun cache disque, aucune BDD.

Invariant: le cache ne doit jamais masquer un XML modifie.

### P1 - Overlays recalcules par graphe

Les paliers de vitesse, bandes de phase et labels sont reconstruits dans chaque graphe temps.

Plan:
- memoizer les overlays statiques par analyse;
- separer overlays statiques et overlays marqueurs;
- garder la vitesse non lissee et les paliers visibles.

Invariant: rendu equivalent visuellement, pas de suppression de paliers.

## P2 a traiter apres validation P0/P1

- Tester `scattergl` seulement sur les graphes `kind === "scatter"` si P0/P1 ne suffisent pas.
- Eventuellement reduire le bundle Plotly plus tard, mais ce n'est pas la cause principale du lag interaction.
- Decouper `MetaSoftChart.tsx` seulement si necessaire pour eviter d'ajouter de la complexite dans un composant deja gros.

## Checks attendus

Python:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_metasoft_local_core.py tests/test_metasoft_audit_export.py tests/test_metasoft_main_session_export.py tests/test_metasoft_local_api.py tests/test_metasoft_ui_helpers.py
```

React:

```bash
cd local_ui && npm run build
```

Smoke manuel:
- ouvrir un XML leger puis un XML plus gros;
- verifier premier rendu, scroll, hover, zoom, double-clic reset;
- placer/deplacer SV1, SV2, VO2max, VMA;
- sauvegarder marqueurs, reporter profil, exporter JSON;
- verifier qu'aucun appel API n'est fait pendant hover/drag.

Critere GO: hover et drag perceptiblement fluides, sans changement des valeurs officielles Python.
