# 📝 PromptoDYS

> **Assistant IA dédié à l'aide scolaire pour élèves avec troubles DYS**

![Version](https://img.shields.io/badge/version-1.3.0b1-blue)
![Python](https://img.shields.io/badge/python-3.14-green)
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
- 💾 Sauvegarde automatique dans `reports/`

### 🎨 Interface adaptée
- 🖼️ Support des images dans les notes
- 📐 Support des formules mathématiques
- 🎨 Titres colorés pour meilleure lisibilité
- 🚫 Évite l'italique (difficile pour les DYS)

### 🤖 Powered by Google Gemini
- ⚡ Modèle Gemini 3.8 Flash
- 💭 Niveau de réflexion configurable (LOW par défaut, économe en tokens)
- 📊 Statistiques de tokens détaillées
- 🔄 Streaming en temps réel

---

## 🚀 Installation

> **Vous voulez seulement utiliser l'application ?** Téléchargez le zip de la dernière version dans les [Releases](https://github.com/lecinquiemejour-code/PromptoDYS_app/releases), puis suivez le fichier `LISEZMOI.txt` qu'il contient. La suite de cette section s'adresse aux développeurs.

### Prérequis

- **[uv](https://docs.astral.sh/uv/)** (gestion de Python, des dépendances et de l'environnement virtuel)
- **Python 3.14** : rien à installer. uv télécharge son propre Python (version figée dans `.python-version`, Tkinter inclus) et ignore volontairement le Python du système ou de Homebrew (`python-preference = "only-managed"` dans `pyproject.toml`)
- **Chrome/Chromium** (pour l'interface Eel)
- **Clé API Google Gemini** ([Obtenir une clé](https://ai.google.dev/))

### Installation des dépendances

```bash
# 1. Cloner le dépôt
git clone https://github.com/lecinquiemejour-code/PromptoDYS_app.git
cd PromptoDYS_app

# 2. Créer l'environnement virtuel (.venv) et installer les dépendances
#    --locked : installe exactement les versions de uv.lock, sans jamais le modifier
uv sync --locked
```
Si `uv sync --locked` échoue, c'est que `uv.lock` n'est plus à jour par rapport à `pyproject.toml` dans le dépôt : signalez-le plutôt que de le régénérer de votre côté.

Les dépendances directes sont déclarées dans `pyproject.toml`. Le fichier `uv.lock` fige toutes les versions (transitives incluses) avec leurs hashes.
Pour mettre à jour une dépendance : `uv lock --upgrade-package <paquet>` puis `uv sync`, et committer `uv.lock`.
Pour ajouter une dépendance : `uv add <paquet>` puis committez `pyproject.toml` ET `uv.lock`.

### Configuration

```bash
# 1. Copier le template de configuration
# Windows
copy GeminiKey.txt.template GeminiKey.txt
# MacOS / Linux
cp GeminiKey.txt.template GeminiKey.txt

# 2. Éditer GeminiKey.txt et remplacer par votre vraie clé API
# IMPORTANT: Ne commitez JAMAIS ce fichier !
```

---

## 📖 Utilisation

### Lancement de l'application

```bash
uv run python askGeminiPrompto.py
```

L'application ouvre un panneau de contrôle, depuis lequel on lance l'éditeur Markdown :
1. **Panneau de contrôle** : boutons « Ouvrir l'Éditeur », « Sauvegarder », « Ouvrir », « Traiter la prise de note », « Voir les rapports PDF » et « Quitter », avec une barre de statut et une zone Console / Logs
2. **Éditeur Markdown** : interface React où l'élève saisit sa note

### Workflow typique

1. **Saisir une note** dans l'éditeur graphique
2. **Lancer le traitement IA** (bouton « Traiter la prise de note », qui devient « Abandonner » pendant le traitement)
3. **L'IA analyse et corrige** la note en temps réel
4. **Le résultat** est injecté automatiquement dans l'éditeur
5. **Un rapport PDF** est généré automatiquement dans `reports/`

---

## 🏗️ Architecture

```
PromptoDYS/
├── askGeminiPrompto.py       # Script principal
├── pyproject.toml            # Dépendances directes et configuration uv
├── uv.lock                   # Versions figées de toutes les dépendances (généré par uv)
├── .python-version           # Version de Python utilisée par uv
├── PromptoDYS.spec           # Configuration PyInstaller
├── promptodys.prompt         # Template de prompt IA
├── GeminiKey.txt.template    # Modèle de GeminiKey.txt
├── LISEZMOI.txt              # Notice d'installation livrée dans le zip
├── GeminiKey.txt             # Clé API (à créer, ignoré par Git)
├── build_web/                # Interface React compilée
│   ├── index.html
│   ├── config.yaml
│   └── static/
├── doc/                      # Documentation technique
├── reports/                  # Rapports PDF générés
└── data/                     # Données utilisateur
```

### Stack technologique

**Backend:**
- Python 3.14
- Eel (bridge Python ↔ Web)
- Google GenAI SDK
- ReportLab (génération PDF)

**Frontend:**
- React
- HTML/CSS/JavaScript

**IA:**
- Google Gemini 3.8 Flash

---

## 📦 Build (Exécutable Windows)

Quel que soit votre système (Windows, macOS ou Linux), utilisez de préférence l'intégration continue : l'exécutable est construit sur une machine Windows propre, avec exactement les versions de `uv.lock`.

### 🔄 Intégration continue (recommandé)

Le workflow GitHub Actions [release-windows.yml](.github/workflows/release-windows.yml) construit l'exécutable sur un runner Windows :
- **Release** : pousser un tag de version (`git tag v1.3.0b1` puis `git push origin v1.3.0b1`). Le zip `PromptoDYS-v1.3.0b1.zip` (exe, `GeminiKey.txt.template` et `LISEZMOI.txt`) est publié dans les Releases GitHub, marqué « Pre-release » pour une beta ou une rc. Voir [CONTRIBUTING.md](CONTRIBUTING.md#publier-une-version).
- **Build de test** : onglet Actions › Release Windows › Run workflow, puis télécharger l'artefact en bas de la page du run. Le zip contient directement `PromptoDYS.exe`, `GeminiKey.txt.template` et `LISEZMOI.txt`, et aucune Release n'est publiée.

### 🛠️ Build en local

PyInstaller produit un exécutable pour le système qui le lance : ces commandes ne donnent un `.exe` que sur Windows (sur macOS, on obtient un exécutable macOS).

```bash
# PyInstaller est dans le groupe "dev" (installé par défaut avec uv sync)
# --locked : le build utilise exactement les versions testées de uv.lock.
uv sync --locked
uv run pyinstaller --clean PromptoDYS.spec

# L'exécutable sera dans dist/PromptoDYS.exe
```

---

## 🎓 Template de prompt (promptodys.prompt)

Le fichier `promptodys.prompt` définit le comportement de l'IA :

- **Rôle** : Assistant dédié aux troubles DYS
- **Matières supportées** : Français, Maths, Histoire-Géo, Sciences, Langues, etc.
- **Fidélité** : aucune information de la note n'est supprimée ni ajoutée, les doutes sont signalés plutôt que corrigés
- **Format de sortie** : 7 sections générées par Gemini
  1. Titre (Matière + Sujet + Date)
  2. Résumé en 1 phrase
  3. 8 mots-clés
  4. Note corrigée
  5. Avertissement IA
  6. Doutes/interrogations
  7. 3 questions d'approfondissement
- **Note originale** : ajoutée automatiquement par l'application à la suite (copie exacte, sans les images)

En développement, le fichier est lu dans le dossier du script à chaque traitement. L'exécutable utilise uniquement la copie embarquée lors du build : un `promptodys.prompt` placé à côté de l'exe est ignoré, et toute modification du prompt demande de relancer le build.

---

## 🔒 Sécurité

⚠️ **IMPORTANT** : Ne commitez JAMAIS votre clé API !

Le fichier `.gitignore` protège automatiquement :
- `GeminiKey.txt`
- `/data` (données utilisateur)
- `reports/` (rapports générés)
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

## 📚 Documentation technique

Le dossier [doc/](doc/) contient la documentation détaillée, avec schémas :

- [ARCHITECTURE.md](doc/ARCHITECTURE.md) : comment les deux projets (application Python et éditeur React) coopèrent, le pont Eel, la sauvegarde des documents, la chaîne de fabrication de l'exécutable.
- [WORKFLOW_GEMINI.md](doc/WORKFLOW_GEMINI.md) : le traitement IA étape par étape, construction du prompt, paramètres Gemini, streaming et abandon, extraction de la réponse, rapport PDF, gestion des erreurs.

---

## 📝 Changelog

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique des versions.

---

## 📄 License

Ce projet est sous licence GPL v3 - voir [LICENSE](LICENSE) pour plus de détails.

---

## 👤 Auteur

**Jean-Noël Lefebvre**

- GitHub: [@lecinquiemejour-code](https://github.com/lecinquiemejour-code)

---

## 🙏 Remerciements

- [Google Gemini](https://ai.google.dev/) pour l'API IA
- [Eel](https://github.com/python-eel/Eel) pour le bridge Python-Web
- [ReportLab](https://www.reportlab.com/) pour la génération PDF

---

## 📞 Support

Pour toute question ou problème :
- Ouvrez une [issue](https://github.com/lecinquiemejour-code/PromptoDYS_app/issues)
- Contactez-moi directement

---

<div align="center">
  <strong>Fait avec ❤️ pour aider les élèves DYS</strong>
</div>
