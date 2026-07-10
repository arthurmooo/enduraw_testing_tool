# Audit packaging et persistance locale

Date : 2026-07-10  
Branche auditée : `feature/metasoft-react-local-ui` (`d55909d`)  
Priorité : PC Windows 11 neuf de Kylian, utilisateur non technique, zéro dépendance installée. Mac/Thibaut vient en second.

## 1 Résumé exécutif

Audit strictement en lecture seule du code, des assets et de l'historique Git. Aucune session, export, BDD ou configuration réelle n'a été modifié. Le seul fichier créé est ce rapport.

**Conclusion immédiate : NO-GO pour livrer aujourd'hui à Kylian.** Le dépôt n'a plus de recette de build Windows actuelle, le chemin des données dépend de l'emplacement de l'exécutable, le build React n'est pas déclaré comme ressource packagée et le launcher Mac actuel dépend du repo et de sa `.venv`. Un PC neuf ne peut donc pas installer et lancer le produit avec un setup unique fiable.

La cible produit est réalisable sans retirer de feature : un unique `EndurawTestingTool-Setup.exe`, installation per-user sans admin si possible, icônes Bureau et Menu Démarrer, lancement sans terminal, données persistantes sous `%LOCALAPPDATA%\EndurawTestingTool`, désinstallation qui ne supprime jamais ces données. Le poste Kylian ne doit nécessiter ni Python, ni Node/npm, ni Git, ni MongoDB local. Edge, fourni avec Windows 11, peut afficher l'UI React locale.

La cible technique minimale est PyInstaller `--onedir --windowed` contenu dans un unique installateur Inno Setup. Le livrable utilisateur reste un seul setup, tandis que l'installation interne `onedir` démarre plus vite et déclenche généralement moins de faux positifs antivirus qu'un exécutable PyInstaller `onefile`.

## 2 État historique du stockage

- `fa3df2a` crée le socle; `d4c4985` introduit le mode session et le calcul de chemin encore présent aujourd'hui. `SessionManager` reçoit le parent du dossier de `src/main_session.py` ou de l'exécutable (`src/main_session.py:993-1001`).
- `5b317cd` ajoute le premier `scripts/build.ps1`; `954d933` puis `ecf8fc3` ajoutent/ajustent le spec PyInstaller. Il ne contenait que `datas=[('src', 'src')]`, sans frontend React.
- `d1accf5` supprime le spec et `scripts/build.ps1` comme obsolètes. Le `README.md:17-43` les documente pourtant encore.
- `9cad02d` ajoute `MongoService` et `ProtocolStore` sur la même racine que les sessions, donc près du code/exécutable (`src/core/mongo_service.py:42-105`, `src/core/protocol_store.py:24-27`).
- `5c4034d` ajoute `run.sh`; le launcher Mac ultérieur reste un simple shell pointant vers le repo d'Arthur (`Enduraw Testing Tool.app/Contents/MacOS/EndurawTestingTool:4-11`). Il n'embarque aucun runtime.
- `34c08c6` ajoute l'UI React locale après la suppression du packaging. Aucun spec post-React n'embarque `local_ui/dist`.
- `56e61c9` ajoute `running_economy_manual.json`; `c496fee` rend seulement `matches.json` atomique; `d55909d` ajoute la preuve MetaSoft `schema_version=1`.

La dette structurante existe donc depuis le mode session initial : une seule variable sert implicitement de racine de code, de ressources, de config et de données. L'ajout de Mongo, protocoles, EC et React a augmenté l'impact sans redéfinir cette racine.

## 3 État actuel du stockage

`main.py:26-38` choisit comme racine de code le dossier de `sys.executable` en mode frozen, sinon le dossier de `main.py`. `TCPDataProcessorSession` refait ensuite son propre calcul puis passe **le parent** aux trois stores (`src/main_session.py:993-1001`).

| Contexte | Racine de données effective aujourd'hui | Conséquence |
|---|---|---|
| Mac en dev | `/Users/arthurmo/Developer/Enduraw/code/enduraw_testing_tool` | `sessions/`, `mongo_config.json`, `protocols.json` vivent dans le repo. |
| Launcher Mac actuel | même repo, chemin codé en dur | fonctionne seulement avec ce repo et son environnement Python. |
| Vrai bundle Mac frozen inchangé | `<App>.app/Contents` | données dans le bundle installé, fragiles lors d'une update et potentiellement non inscriptibles/signables. |
| Windows per-user inchangé | exe sous `%LOCALAPPDATA%\Programs\EndurawTestingTool`, données sous `%LOCALAPPDATA%\Programs` | mélange programmes/données et collision possible avec d'autres apps. |
| Windows sous `C:\Program Files` inchangé | `C:\Program Files` | écriture normalement refusée sans élévation. |
| exe portable sur le Bureau | `C:\Users\Kylian` | données créées à un endroit surprenant et indépendant du dossier de l'exe. |

Le serveur React cherche ses assets via `Path(__file__).resolve().parents[2] / "local_ui" / "dist"` (`src/local_api/metasoft_server.py:164-165`). Cela marche dans le repo. En frozen, `local_ui/dist` doit être explicitement embarqué au même layout dans la racine de ressources PyInstaller; ce cas n'est ni configuré ni testé.

Le runtime à embarquer comprend Python, Tcl/Tk, CustomTkinter, pymongo, pydantic/email-validator, matplotlib et leurs dépendances (`requirements.txt:3-16`), ainsi que le build React. Node, npm, Git et PyInstaller sont des outils de build uniquement. MongoDB reste distant : seul `pymongo` et l'accès réseau sont requis. `webbrowser.open` existe déjà (`src/main_session.py:815-825`), donc Edge peut servir l'UI sans webview ni navigateur embarqué.

Le `README.md:17-43` propose un ancien build `onefile` ajoutant seulement `src`; le spec historique `ecf8fc3` est antérieur à React. Le packaging actuel est donc **incomplet et non reproductible**.

## 4 Données locales à préserver

`SessionManager` définit la structure aux lignes `src/core/session_manager.py:69-95` et crée une session aux lignes `107-155`. Tout ce tableau est de la donnée utilisateur à sauvegarder/migrer, sauf les ressources explicitement marquées code.

| Élément | Contenu / écriture | Exigence de préservation |
|---|---|---|
| `sessions/<session>/session.json` | nom, date, lieu, description, `created_at` | préserver octet pour octet; pas de version actuelle. |
| `sessions/<session>/profiles/*.json` | profils coach/athlète et marqueurs reportés | critique; ajout/mise à jour directs (`229-357`). |
| `sessions/<session>/xml/*.xml` | copies des XML importés | source métier critique; import avec suffixe anti-écrasement (`418-446`). |
| `sessions/<session>/matches.json` | associations profil/XML, export, preuve `metasoft_report` | critique; remplacement atomique (`511-526`), preuve `schema_version=1` (`695-748`). |
| `sessions/<session>/running_economy_manual.json` | EC par `match_id`, fingerprint et données | critique; écriture directe (`763-820`). |
| `sessions/<session>/output/*.json` | JSON final Valentin | préserver tous les exports et leurs dates. |
| `*.metasoft_audit.json` dans `output/` | sidecars d'audit | préserver avec le JSON associé; nom défini dans `src/core/metasoft_audit_export.py:20-28`. |
| `mongo_config.json` | URI, DB, collection en clair | migrer sans loguer le secret; fichier actuel aux lignes `src/core/mongo_service.py:42-105`. |
| `.env` | URI/DB/collection optionnels | ne jamais embarquer; import explicite seulement si besoin. |
| `protocols.json` | protocoles créés par l'utilisateur | préserver; store aux lignes `src/core/protocol_store.py:24-27,88-103`. |
| `src/config.py` | version/constantes | ressource de code, pas donnée utilisateur; `APP_VERSION=1.0.0` (`5-7`). |
| `local_ui/dist/` | HTML/CSS/JS compilés | ressource de code, pas donnée utilisateur; environ 4,9 Mo observés et ignorés par Git (`.gitignore:13-15`). |
| cache/token API | cache de contexte/token process | mémoire uniquement (`src/local_api/metasoft_server.py:33-51`), rien à migrer. |
| `Output/` de `JsonExporter` | ancien chemin relatif | vérifier/importer s'il existe; le flux session actuel utilise `SessionManager.save_output` (`src/utils/json_exporter.py:13-39`). |

Le repo contient un exemple complet d'environ 15 Mo sous `sessions/2026-07-08_contas` : 3 XML, 2 profils, matches, EC et 2 outputs. Les sessions sont ignorées par Git (`.gitignore:37-38`), donc Git ne constitue ni sauvegarde ni mécanisme d'update.

## 5 Risques de perte de données

**P0 — mauvaise racine.** Un bundle Mac écrirait dans son propre `.app`; Windows peut écrire sous `Program Files`, `%LOCALAPPDATA%\Programs` ou le parent d'un exe portable. Une update, un déplacement ou un manque de droits peut faire disparaître les données de la vue de l'app, empêcher l'écriture ou remplacer le code qui les contient.

**P0 — package incomplet.** Aucun packaging actuel ne garantit Python/dépendances/React dist. Un démarrage partiel peut donner une app Tk disponible mais une analyse React absente.

**P1 — écritures directes.** `session.json`, profils, outputs, EC, protocoles et config ne suivent pas encore le remplacement atomique de `matches.json`; coupure ou disque plein peuvent produire un JSON partiel. Les outputs de même nom sont réécrasés (`src/core/session_manager.py:605-626`).

**P1 — erreurs silencieuses.** Un JSON session invalide est ignoré dans les listes (`src/core/session_manager.py:189-213`), une EC invalide devient `{}` (`804-815`) et `MongoService`/`ProtocolStore` avalent des erreurs. L'utilisateur peut croire ses données absentes sans diagnostic.

**P1 — secret local.** `mongo_config.json` conserve l'URI en clair. Elle ne doit ni entrer dans le setup, ni les manifests, ni les logs. Windows Credential Manager/macOS Keychain est la cible de sécurité, à arbitrer pour V1.

**P1 — suppression irréversible.** L'UI appelle `shutil.rmtree` après une confirmation simple (`src/main_session.py:232-242`, `src/core/session_manager.py:215-225`). Aucun backup automatique ni corbeille n'existe.

**P1 — absence de visionneuse.** L'UI liste/ouvre/supprime les sessions, mais n'affiche ni racine réelle, ni intégrité, ni historique d'outputs, ni résultat de migration. Ce manque est critique pour Kylian, qui ne doit pas diagnostiquer des JSON dans l'Explorateur.

## 6 Stockage cible Mac / Windows

Séparer deux fonctions : `resource_root` immuable pour code/React/assets, et `user_data_root` inscriptible pour tous les stores. Aucun store ne doit dériver son chemin de `sys.executable` ou `__file__` directement.

| Plateforme | Code uniquement | Données persistantes |
|---|---|---|
| Windows | `%LOCALAPPDATA%\Programs\EndurawTestingTool\` | `%LOCALAPPDATA%\EndurawTestingTool\` soit `C:\Users\Kylian\AppData\Local\EndurawTestingTool\` |
| Mac | `/Applications/Enduraw Testing Tool.app` ou `~/Applications/...` | `~/Library/Application Support/EndurawTestingTool/` |

Structure cible commune : `sessions/`, `backups/`, `logs/`, `protocols.json`, `mongo_config.json` ou référence credential store, `data_schema.json`, `migration_state.json`. Les logs Mac peuvent aussi être exposés sous `~/Library/Logs/EndurawTestingTool/`.

Windows cible : PyInstaller `--onedir --windowed` inclut runtime Python, toutes les dépendances, `local_ui/dist` et icône; Inno Setup produit un seul setup avec `PrivilegesRequired=lowest`, raccourcis Bureau/Menu Démarrer et désinstallation code-only. Aucun terminal ne doit apparaître. Edge système affiche l'URL locale.

Mac cible secondaire : vrai bundle autonome contenant runtime et React dist, idéalement signé/notarisé. Le launcher actuel à chemin absolu n'est pas distribuable à Thibaut.

## 7 Plan de migration proposé

Au premier lancement de la nouvelle version :

1. créer la nouvelle racine et prendre un verrou de migration;
2. inventorier les racines legacy en lecture seule; proposer un sélecteur si l'ancien exe était portable;
3. produire un manifest chemins/tailles/SHA-256, sans URI Mongo;
4. copier une **sauvegarde datée** sous `backups/legacy-YYYYMMDD-HHMMSS/` avant activation;
5. valider parsing JSON et hashes des copies;
6. copier vers la cible **sans jamais écraser** un fichier existant;
7. session homonyme identique : marquer déjà importée; différente : copier sous `<nom>__legacy_<timestamp>` et consigner le conflit;
8. config/protocole cible existant : conserver la cible, garder la variante legacy dans le backup et signaler le conflit;
9. écrire atomiquement `migration_state.json` seulement après validation complète;
10. au rerun, relire le manifest et ne copier que les absents; **ne jamais supprimer ni déplacer l'ancienne racine**.

Sources prioritaires : repo actuel du Mac d'Arthur, ancien parent d'exécutable si détectable, et dossier choisi manuellement pour un ancien Windows portable. Une migration échouée doit afficher une erreur actionnable, pas une liste vide.

Ajouter en même temps une visionneuse read-only « Données locales » : chemin réel, schéma, sessions, dates, nombres de profils/XML/matches/outputs, présence EC/audit, taille, modification, anomalies, backup et conflits. Actions sûres : « Ouvrir dans l'Explorateur/Finder », lire un output, exporter une archive support redacted. Aucun éditeur JSON. La suppression reste séparée avec double confirmation ou nom saisi.

Tests migration obligatoires : cible vide, rerun idempotent, session identique, conflit, JSON corrompu, disque plein, interruption, URI secrète. Chaque cas doit prouver que la source legacy reste intacte.

## 8 Plan d’update futur

Créer `data_schema.json` avec `schema_version`, `created_by_app_version`, `last_migrated_by_app_version` et historique. Les migrations sont additives et versionnées. Aujourd'hui, seule la preuve MetaSoft porte `schema_version=1`; session, profils, EC et protocoles n'ont pas de version globale.

L'upgrade conserve le même AppId installateur et remplace uniquement le code. L'uninstaller retire programme/raccourcis mais **jamais** `%LOCALAPPDATA%\EndurawTestingTool`. Une future action « Supprimer mes données » doit être séparée, décochée par défaut, explicitement confirmée et précédée d'un backup.

Étendre le remplacement atomique de `matches.json` aux autres JSON critiques et rendre les erreurs visibles/journalisées sans secret. Conserver des noms d'outputs uniques ou un historique au lieu d'écraser silencieusement.

Préparable sur Mac : resolver/tests mockés, migration, spec PyInstaller, script Inno `.iss`, workflow GitHub Actions, build React, manifest/hashes, icône, docs et bundle Mac. Le Mac ne peut pas compiler/valider de façon fiable le bootloader PyInstaller Windows ni l'installateur Inno.

À faire sur Windows ou GitHub Actions `windows-latest` : `npm ci && npm run build`, environnement Python propre, PyInstaller onedir incluant `local_ui/dist`, compilation Inno et publication du setup avec hash. La signature Authenticode nécessite un certificat; sans elle SmartScreen reste un risque terrain.

Validation update sur Windows 11 propre : install sans admin, raccourcis, aucun terminal, démarrage hors repo, session persistante après fermeture, XML/React Edge/report/export, upgrade conservant les données, désinstallation/réinstallation conservant les données, aucun Python/Node/Git/Mongo local et logs exploitables. Rejouer ensuite l'équivalent sur un Mac propre.

## 9 Questions ouvertes

- Qui saisit l'URI Mongo sur le poste de Kylian ? Faut-il Windows Credential Manager dès V1 plutôt qu'un JSON en clair ? L'URI ne doit jamais être embarquée.
- Un certificat Authenticode Enduraw est-il disponible pour éviter l'alerte SmartScreen ?
- La visionneuse affiche-t-elle le JSON formaté ou uniquement un résumé métier et « Ouvrir le fichier » ?
- Où se trouvent les éventuelles anciennes données Windows; faut-il toujours afficher un sélecteur au premier lancement ?
- Quelle rétention pour backups/logs ? Recommandation initiale : aucune suppression automatique avant validation terrain.
- Le raccourci Bureau doit-il être obligatoire ou proposé/coché par défaut ? Le Menu Démarrer doit être systématique.

Ces questions ne bloquent pas l'implémentation de la séparation des chemins, du package autonome, de la migration non destructive et de la visionneuse read-only.

## 10 Recommandation GO / NO-GO avant packaging Windows/Mac

**Verdict actuel Kylian/Windows : NO-GO.**  
**Verdict actuel Thibaut/Mac propre : NO-GO.** Le launcher présent n'est qu'un raccourci vers le repo d'Arthur.  
**GO conditionnel de l'architecture proposée : OUI**, après validation des critères ci-dessous.

Ordre minimal : (1) séparer ressources/données; (2) ajouter schéma, migration, backups et logs; (3) résoudre React dist frozen; (4) produire PyInstaller onedir; (5) produire Inno Setup per-user; (6) ajouter la visionneuse; (7) automatiser le build Windows; (8) tester sur Windows 11 neuf; (9) seulement ensuite produire le bundle Mac autonome.

GO Windows uniquement si : un setup unique s'installe per-user sans dépendances/admin; les deux raccourcis fonctionnent sans terminal; React s'ouvre dans Edge; toutes les features/report/export fonctionnent; les données vont exclusivement sous `%LOCALAPPDATA%\EndurawTestingTool`; migration/rerun/conflits sont non destructifs; upgrade et uninstall ne suppriment rien; build reproductible et idéalement signé.

GO Mac uniquement si : bundle autonome hors repo/.venv; données exclusivement sous Application Support; React dist embarqué; migration validée; update et suppression de l'app conservent les données; signature/notarisation arbitrées.

Risques restant à traiter avant GO : P0 séparation data/code, P0 assets React/package autonome, P0 installateur reproductible; P1 atomicité/erreurs silencieuses, URI en clair, signature Windows et visionneuse; P2 poids/démarrage. `onedir` dans un setup répond au dernier sans dégrader l'expérience « un seul fichier à installer ».
