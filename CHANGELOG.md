# Changelog - PromptoDYS

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et la numérotation suit le sens du [Semantic Versioning](https://semver.org/lang/fr/) (MAJEUR.MINEUR.CORRECTIF),
écrite au format Python ([PEP 440](https://peps.python.org/pep-0440/)) : pré-versions `1.3.0b1`, `1.3.0rc1`, tags git `v1.3.0b1`.

---

## [Non publié]

### Ajouté
- Tests automatisés avec pytest (`uv run pytest`) : import du module sans effet de bord, extraction de la note et du débrief, ajout de la note d'origine, nettoyage HTML pour le rapport PDF, chemins de sauvegarde. pytest-timeout fait échouer au bout de 10 s un test qui boucle
- Lint avec ruff (`uv run ruff check`), installé dans le groupe `dev` et configuré dans `pyproject.toml` : règles `F`, `E`, `W`, `B`, `UP` et `SIM`, lignes de 120 caractères au plus. Le code a été mis en conformité (corrections automatiques sûres, ordre des imports, lignes trop longues) ; quelques signalements restent à traiter, dont les `except:` nus
- Workflow GitHub Actions d'intégration continue (`.github/workflows/ci.yml`) : à chaque push, sur toutes les branches, lint ruff, tests pytest et build de l'exécutable Windows, avec un résumé en haut de chaque exécution (signalements ruff par règle, tests en échec, résultat du build). Badge d'état de `master` dans le README

### Modifié
- L'abandon du traitement IA est immédiat, même si Gemini ne répond plus : l'interface est libérée sans attendre la fin de l'appel, et un traitement abandonné s'arrête avant l'injection dans l'éditeur et le rapport PDF
- Le statut affiché en fin de traitement IA indique « terminé », « annulé » ou « échec » selon le résultat
- La fenêtre de contrôle prend la taille de son contenu au lieu de 688 × 1100 px en dur. Sa hauteur est plafonnée à 90 % de l'écran ; si l'écran est trop petit, la fenêtre défile
- Les dossiers de l'application (documents, profil Chrome) sont créés au démarrage et non plus à l'import du module
- Pendant l'ouverture de l'éditeur, le statut indique « Ouverture de l'éditeur en cours, veuillez patienter », et « Éditeur ouvert » ne s'affiche que lorsque l'éditeur est réellement prêt. Un second clic pendant l'ouverture ne lance plus un second éditeur

### Corrigé
- Le bouton « Traiter la prise de note » restait bloqué sur « Abandonner » après un échec avant le streaming (clé API absente par exemple), avec un faux statut « terminé ». Le failsafe censé le débloquer plantait lui-même sur une option Tkinter invalide
- Un échec de l'ouverture de l'éditeur provoquait un `NameError` au lieu d'afficher le message d'erreur
- `GeminiKey.txt`, `reports/` et `build_web/` étaient cherchés dans le dossier courant : lancée depuis un raccourci ou un autre dossier, l'application ne les trouvait plus. Ils sont désormais cherchés dans le dossier de l'application
- Un nom de document vide ou commençant par un point était accepté à la sauvegarde, et figeait l'application à la racine d'un disque Windows. Il est refusé avec un message, et le dialogue se rouvre
- La fenêtre de contrôle dépassait de l'écran sur un portable 1366 × 768 : la console et le bouton Quitter étaient inaccessibles
- Les boutons « Sauvegarder » et « Ouvrir » grandissaient au premier survol
- La bordure sombre des boutons n'apparaissait qu'après un survol : le thème Sun Valley la repeignait en gris clair au lancement
- Si le port 8080 était déjà utilisé par un autre programme, l'éditeur s'ouvrait sur la page de ce programme, puis une seconde fenêtre s'ouvrait en erreur. Le port est maintenant vérifié avant d'ouvrir Chrome : s'il reste occupé, aucune fenêtre ne s'ouvre et une popup explique quoi faire. Une popup s'affiche aussi si Chrome ne démarre pas
- Ouvrir un document avec le bouton « Ouvrir » quand l'éditeur était fermé échouait toujours après 30 s d'attente : l'éditeur ne signalait jamais son ouverture à l'application
- Après la fermeture de l'éditeur, le panneau de contrôle continuait de le considérer comme ouvert : il était impossible de le rouvrir. L'éditeur signale maintenant sa fermeture, le panneau affiche « Éditeur fermé » et l'éditeur peut être rouvert
- Trois anciennes versions de l'éditeur, inutilisées, étaient embarquées dans l'exécutable

### Prévu
- Tests d'intégration
- Support export DOCX
- Mode offline avec cache local
- Tableau de bord statistiques élèves
- Interface professeurs

---

## [1.3.0b2] - 2026-10-27

### Ajouté
- Notice d'installation pour l'utilisateur final (`LISEZMOI.txt`), incluse dans le zip de release et citée dans les notes de Release : extraction du zip, création de la clé API Gemini et de `GeminiKey.txt`, premier lancement, résolution des problèmes courants

### Modifié
- Renommé : `.env.template` → `GeminiKey.txt.template`. Le nom ne commence plus par un point et indique le fichier à créer

---

## [1.3.0b1] - 2026-10-21

### Ajouté
- Workflow GitHub Actions de build et de release de l'exécutable Windows (`.github/workflows/release-windows.yml`) : un tag `v*` publie une Release contenant `PromptoDYS.exe` et `.env.template`

### Modifié
- Gestion des dépendances et de l'environnement Python avec `uv` (`pyproject.toml` + `uv.lock`)
- Python 3.14 requis, fourni par uv (`python-preference = "only-managed"`)
- Montées de version majeures : `google-genai` 1.59 → 2.31, `reportlab` 4.4 → 5.0, `gevent` 25.9 → 26.9
- Documentation d'installation et de build mise à jour pour uv (`uv sync --locked`, `uv run`)
- Amélioration de la logique de chargement de l'API Key Gemini : lignes vides et commentaires ignorés, fichier enregistré avec BOM (Bloc-notes Windows) accepté, message clair si la valeur du template n'a pas été remplacée par l'utilisateur
- Migration de Gemini 2.5 Flash vers `gemini-3.8-flash` : niveau de réflexion `thinking_level` LOW à la place de `thinking_budget`, paramètres `temperature` et `max_output_tokens` retirés (ignorés par Gemini 3)
- Modèle et niveau de réflexion extraits en constantes `GEMINI_MODEL` et `GEMINI_THINKING_LEVEL`, repris dans les logs et le pied du rapport PDF
- Prompt `promptodys.prompt` : règles de fidélité au contenu, reformulation et réorganisation explicites, sous-parties sans titre `####`, titre « Note corrigée » obligatoire, doutes établis en comparant la note corrigée à la note d'origine, nouvelle règle de mise en page des lignes
- La note d'origine est ajoutée par l'application au lieu d'être recopiée par Gemini : copie exacte, et environ 27 % de tokens de sortie en moins (13 % du total) sur la note de test
- `prompto.dys` renommé en `promptodys.prompt`. L'exécutable utilise uniquement le prompt embarqué (un fichier placé à côté de l'exe est ignoré) ; en développement, le prompt est lu dans le dossier du script et non plus dans le dossier courant

### Supprimé
- `requirements.txt` (encodé en UTF-16), remplacé par `pyproject.toml` et `uv.lock`
- Constante `__version__`, jamais lue : la version de référence est celle de `pyproject.toml`
- `BUILD_STATUS.md`, obsolète (problème propre à Python 3.10.0)
- Code mort : menu console (`menu_console()`, `lire_contenu()`, `ecrire_contenu()`), jamais appelé depuis le passage au panneau Tkinter
- Code mort : historique de session (`historique_llm`, `ajouter_message_llm()`), rempli à chaque traitement mais jamais lu, et variable globale `web_folder_global`, utilisée uniquement dans `main()`
- Imports inutilisés `markdown`, `PageBreak` et `TableOfContents`, et dépendance `markdown` retirée de `pyproject.toml`, `uv.lock` et des `hiddenimports` de `PromptoDYS.spec`

### Sécurité
- Paramètres de sécurité pour Claude Code (`.claude/settings.json`) : lecture de `GeminiKey.txt` interdite, confirmation demandée pour les commandes destructives et les changements de dépendances
- Le log de chargement de la clé API, recopié dans les rapports PDF, n'affiche plus que les 4 derniers caractères de la clé au lieu des 10 premiers
- `GeminiKey.txt` n'est plus inclus dans l'exécutable : chaque utilisateur fournit sa propre clé à côté de l'exe

---

## [1.2.0] - 2026-01-21

### Ajouté
- Métadonnées Windows complètes pour l'exécutable (version_info)
- Documentation anti-antivirus (`README_ANTIVIRUS.md`)
- Hash SHA256 pour vérification d'intégrité
- Constante `__version__` dans le code Python

### Modifié
- Configuration PyInstaller : UPX désactivé pour réduire les faux positifs antivirus
- Procédure de build mise à jour avec étapes anti-détection
- Optimisations de compilation pour meilleure compatibilité antivirus

### Amélioré
- Fiabilité de la détection de l'état de l'éditeur
- Système de logging avec capture complète
- Gestion des processus et tracking temporel

---

## [1.1.0] - 2026-01-08

### Ajouté
- Configuration Git et GitHub complète
- Documentation avancée (README, CONTRIBUTING, LICENSE)
- Template de configuration `.env.template`
- Fichier `.gitignore` complet pour sécurité
- Normalisation des fins de ligne (`.gitattributes`)
- Analyse complète du projet dans `analyse_projet_promptodys.md`

### Sécurité
- Protection de la clé API via `.gitignore`
- Exclusion des données utilisateur du versioning
- Exclusion des rapports générés

---

## [1.0.0] - 2025-11-07

### Ajouté
- Application desktop avec interface Eel
- Intégration Google Gemini 2.5 Flash
- Mode "thinking" pour analyse approfondie IA
- Génération automatique de rapports PDF avec ReportLab
- Template de prompt spécialisé troubles DYS (`prompto.dys`)
- Menu console interactif (3 options)
- Capture complète des logs dans les rapports
- Support des images dans les notes
- Support des formules mathématiques
- Compilation PyInstaller pour exécutable Windows
- Configuration développeur via `config.yaml`

### Structure
- Interface React compilée dans `build_web/`
- Système de sauvegarde automatique dans `reports/`
- Gestion des données utilisateur dans `/data`

### Fonctionnalités IA
- Correction orthographique et grammaticale
- Amélioration structure et lisibilité
- Mise en forme Markdown automatique
- Détermination automatique de la matière
- Génération de résumé et mots-clés
- Questions d'approfondissement
- Statistiques de tokens (input/output/thinking)

### Adaptation DYS
- Pas d'utilisation d'italique
- Titres colorés (#3399ff)
- Séparateurs horizontaux pour clarté
- Formatage adapté à la dyslexie

---

## [0.9.0] - 2025-11-06 (Beta)

### Ajouté
- Première version fonctionnelle
- Interface graphique basique
- Intégration Gemini basique
- Génération PDF simple

### Problèmes connus
- Balises `<span>` problématiques dans les PDF (corrigé en v1.0.0)
- Émojis non supportés dans certains PDF (corrigé en v1.0.0)

---

## Format des versions

### [X.Y.Z]
- **X** (majeur) : Breaking changes, refonte majeure
- **Y** (mineur) : Nouvelles fonctionnalités, rétrocompatibles
- **Z** (patch) : Corrections de bugs, améliorations mineures

### Catégories de changements
- **Ajouté** : Nouvelles fonctionnalités
- **Modifié** : Changements dans fonctionnalités existantes
- **Déprécié** : Fonctionnalités bientôt supprimées
- **Supprimé** : Fonctionnalités supprimées
- **Corrigé** : Corrections de bugs
- **Sécurité** : Correctifs de vulnérabilités

---

**Lien des releases :** [GitHub Releases](https://github.com/lecinquiemejour-code/PromptoDYS_app/releases)
