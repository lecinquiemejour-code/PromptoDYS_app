# Changelog - PromptoDYS

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

---

## [Non publié]

### Modifié
- Licence du projet : Passage de **MIT** à **GPL v3**.
- Mise à jour des badges et documentation associés.
- Tests unitaires et d'intégration
- Support export DOCX
- Mode offline avec cache local
- Tableau de bord statistiques élèves
- Interface professeurs

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
- Système de sauvegarde automatique dans `/REPORTS`
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

**Lien des releases :** [GitHub Releases](https://github.com/VOTRE_USERNAME/PromptoDYS/releases)
