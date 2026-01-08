# 📝 PromptoDYS

> **Assistant IA dédié à l'aide scolaire pour élèves avec troubles DYS**

![Version](https://img.shields.io/badge/version-1.1-blue)
![Python](https://img.shields.io/badge/python-3.x-green)
![License](https://img.shields.io/badge/license-GPL--3.0-orange)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

PromptoDYS est une application desktop qui combine un éditeur Markdown avec l'intelligence artificielle Google Gemini pour corriger et améliorer automatiquement les prises de notes d'élèves souffrant de troubles DYS (Dyslexie, Dysorthographie, Dysgraphie, Dyspraxie).

---

## ✨ Fonctionnalités

### 🎯 Correction IA automatique
- ✅ Correction orthographique et grammaticale
- ✅ Amélioration de la structure et de la lisibilité
- ✅ Mise en forme Markdown automatique
- ✅ Adaptation spécifique aux troubles DYS

### 📊 Rapports PDF professionnels
- 📄 Génération automatique de rapports détaillés
- 🎨 Styles personnalisés et lisibles
- 📋 Capture complète des logs et statistiques
- 💾 Sauvegarde automatique dans `/REPORTS`

### 🎨 Interface adaptée
- 🖼️ Support des images dans les notes
- 📐 Support des formules mathématiques
- 🎨 Titres colorés pour meilleure lisibilité
- 🚫 Évite l'italique (difficile pour les DYS)

### 🤖 Powered by Google Gemini
- ⚡ Modèle Gemini 2.5 Flash
- 💭 Mode "thinking" pour analyse approfondie
- 📊 Statistiques de tokens détaillées
- 🔄 Streaming en temps réel

---

## 🚀 Installation

### Prérequis

- **Python 3.x** (3.8 ou supérieur recommandé)
- **Chrome/Chromium** (pour l'interface Eel)
- **Clé API Google Gemini** ([Obtenir une clé](https://ai.google.dev/))

### Installation des dépendances

```bash
# 1. Cloner le dépôt
git clone https://github.com/VOTRE_USERNAME/PromptoDYS.git
cd PromptoDYS

# 2. Créer un environnement virtuel
python -m venv .venv

# 3. Activer l'environnement virtuel
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Installer les dépendances
pip install eel google-genai reportlab markdown
```

### Configuration

```bash
# 1. Copier le template de configuration
copy .env.template GeminiKey.txt

# 2. Éditer GeminiKey.txt et remplacer par votre vraie clé API
# IMPORTANT: Ne commitez JAMAIS ce fichier !
```

---

## 📖 Utilisation

### Lancement de l'application

```bash
python askGeminiPrompto.py
```

L'application ouvre deux interfaces :
1. **Interface graphique** : Éditeur Markdown React
2. **Console interactive** : Menu avec 3 options

### Menu console

```
📋 Options:
  1 - Lire le contenu de l'éditeur
  2 - Écrire dans l'éditeur
  3 - 🤖 Traitement de la note par l'IA
  0 - Quitter
```

### Workflow typique

1. **Saisir une note** dans l'éditeur graphique (ou via l'option 2)
2. **Lancer le traitement IA** (option 3)
3. **L'IA analyse et corrige** la note en temps réel
4. **Le résultat** est injecté automatiquement dans l'éditeur
5. **Un rapport PDF** est généré automatiquement dans `/REPORTS`

---

## 🏗️ Architecture

```
PromptoDYS/
├── askGeminiPrompto.py       # Script principal (848 lignes)
├── PromptoDYS.spec           # Configuration PyInstaller
├── prompto.dys               # Template de prompt IA
├── GeminiKey.txt             # Clé API (à créer, ignoré par Git)
├── build_web/                # Interface React compilée
│   ├── index.html
│   ├── config.yaml
│   └── static/
├── REPORTS/                  # Rapports PDF générés
└── data/                     # Données utilisateur
```

### Stack technologique

**Backend:**
- Python 3.x
- Eel (bridge Python ↔ Web)
- Google GenAI SDK
- ReportLab (génération PDF)

**Frontend:**
- React
- HTML/CSS/JavaScript

**IA:**
- Google Gemini 2.5 Flash

---

## 📦 Build (Exécutable Windows)

```bash
# Installer PyInstaller
pip install pyinstaller

# Compiler l'exécutable
pyinstaller PromptoDYS.spec

# L'exécutable sera dans dist/PromptoDYS.exe
```

---

## 🎓 Template de prompt (prompto.dys)

Le fichier `prompto.dys` définit le comportement de l'IA :

- **Rôle** : Assistant dédié aux troubles DYS
- **Matières supportées** : Français, Maths, Histoire-Géo, Sciences, Langues, etc.
- **Format de sortie** : 8 sections structurées
  1. Titre (Matière + Sujet + Date)
  2. Résumé en 1 phrase
  3. 8 mots-clés
  4. Note corrigée
  5. Avertissement IA
  6. Doutes/interrogations
  7. 3 questions d'approfondissement
  8. Note originale

---

## 🔒 Sécurité

⚠️ **IMPORTANT** : Ne commitez JAMAIS votre clé API !

Le fichier `.gitignore` protège automatiquement :
- `GeminiKey.txt`
- `/data` (données utilisateur)
- `/REPORTS` (rapports générés)
- `.venv` (environnement virtuel)

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Consultez [CONTRIBUTING.md](CONTRIBUTING.md) pour les guidelines.

### Processus de contribution

1. Fork le projet
2. Créez une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commitez vos changements (`git commit -m 'Add AmazingFeature'`)
4. Pushez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

---

## 📝 Changelog

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique des versions.

---

## 📄 License

Ce projet est sous licence GPL v3 - voir [LICENSE](LICENSE) pour plus de détails.

---

## 👤 Auteur

**Jean-Noël Lefebvre**

- GitHub: [@VOTRE_USERNAME](https://github.com/VOTRE_USERNAME)

---

## 🙏 Remerciements

- [Google Gemini](https://ai.google.dev/) pour l'API IA
- [Eel](https://github.com/python-eel/Eel) pour le bridge Python-Web
- [ReportLab](https://www.reportlab.com/) pour la génération PDF

---

## 📞 Support

Pour toute question ou problème :
- Ouvrez une [issue](https://github.com/VOTRE_USERNAME/PromptoDYS/issues)
- Contactez-moi directement

---

<div align="center">
  <strong>Fait avec ❤️ pour aider les élèves DYS</strong>
</div>
