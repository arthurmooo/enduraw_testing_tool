# Lot 4 minimal - Launcher desktop Enduraw

Date: 2026-07-08

## Objectif

Ajouter un launcher macOS cliquable pour tester l'app locale sans terminal, avec
le logo Enduraw fourni par Arthur.

Logo source:

- `/Users/arthurmo/Downloads/LOGO_ENDURAW_HORIZONTAL_WHITE.png`

## Scope

- creer une app bundle locale `Enduraw Testing Tool.app`;
- placer une copie sur le Bureau si possible;
- l'app lance `./run.sh` dans le repo courant;
- l'icone finale est embarquee dans `.app/Contents/Resources`, donc pas de
  dependance runtime au fichier dans `Downloads`;
- pas de packaging PyInstaller, pas de notarisation, pas de build Windows dans
  ce lot.

## Contraintes

- aucune ecriture BDD;
- aucun push, aucun stage;
- ne pas modifier `run.sh`;
- ne pas toucher au repo dashboard;
- si la generation `.icns` echoue, garder le launcher fonctionnel et documenter
  l'icone comme restant packaging.

## Verification

- `Enduraw Testing Tool.app` existe;
- `Info.plist` pointe vers l'icone;
- le binaire launcher est executable;
- un lancement manuel via `open` ne doit pas necessiter de terminal.
