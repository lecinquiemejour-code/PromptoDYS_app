# 🤝 Guide de Contribution - PromptoDYS

Merci de votre intérêt pour contribuer à PromptoDYS ! Ce document fournit les guidelines pour contribuer au projet.

---

## 📋 Table des matières

- [Code de conduite](#code-de-conduite)
- [Comment contribuer](#comment-contribuer)
- [Signaler un bug](#signaler-un-bug)
- [Proposer une fonctionnalité](#proposer-une-fonctionnalité)
- [Processus de Pull Request](#processus-de-pull-request)
- [Standards de code](#standards-de-code)
- [Structure des commits](#structure-des-commits)

---

## 📜 Code de conduite

En participant à ce projet, vous acceptez de maintenir un environnement respectueux et inclusif pour tous les contributeurs.

**Comportements attendus :**
- ✅ Utiliser un langage accueillant et inclusif
- ✅ Respecter les points de vue et expériences différents
- ✅ Accepter les critiques constructives avec grâce
- ✅ Se concentrer sur ce qui est meilleur pour la communauté

**Comportements inacceptables :**
- ❌ Langage ou images sexualisés
- ❌ Trolling, insultes ou attaques personnelles
- ❌ Harcèlement public ou privé
- ❌ Publication d'informations privées sans permission

---

## 🚀 Comment contribuer

### Types de contributions recherchées

1. **📝 Documentation**
   - Amélioration du README
   - Ajout d'exemples d'utilisation
   - Traduction en d'autres langues

2. **🐛 Corrections de bugs**
   - Signalement de bugs via Issues
   - Proposition de correctifs

3. **✨ Nouvelles fonctionnalités**
   - Support de nouveaux formats d'export
   - Amélioration de l'interface utilisateur
   - Optimisation des performances

4. **🧪 Tests**
   - Ajout de tests unitaires
   - Tests d'intégration
   - Tests end-to-end

---

## 🐛 Signaler un bug

### Avant de créer une issue

1. **Vérifiez** que le bug n'a pas déjà été signalé dans les [Issues](https://github.com/lecinquiemejour-code/PromptoDYS_app/issues)
2. **Assurez-vous** d'utiliser la dernière version du projet
3. **Collectez** les informations nécessaires (voir ci-dessous)

### Template d'issue pour bug

```markdown
## Description
[Description claire et concise du bug]

## Étapes pour reproduire
1. Aller à '...'
2. Cliquer sur '...'
3. Faire défiler jusqu'à '...'
4. Voir l'erreur

## Comportement attendu
[Ce qui devrait se passer]

## Comportement réel
[Ce qui se passe réellement]

## Environnement
- OS: [ex: Windows 11]
- Python: [ex: 3.10.5]
- Version PromptoDYS: [ex: 1.1]

## Logs
[Coller les logs pertinents ici]

## Captures d'écran
[Si applicable, ajouter des captures d'écran]
```

---

## ✨ Proposer une fonctionnalité

### Template d'issue pour feature request

```markdown
## Problème résolu
[Quel problème cette fonctionnalité résout-elle ?]

## Solution proposée
[Description détaillée de la solution]

## Alternatives considérées
[Autres approches envisagées]

## Impact
- [ ] Modification de l'API
- [ ] Breaking change
- [ ] Nécessite migration
- [ ] Nécessite documentation

## Maquettes/Exemples
[Si applicable, ajouter des maquettes ou exemples de code]
```

---

## 🔄 Processus de Pull Request

### 1. Fork et clone

```bash
# Fork via GitHub UI, puis:
git clone https://github.com/lecinquiemejour-code/PromptoDYS_app.git
cd PromptoDYS
git remote add upstream https://github.com/ORIGINAL_OWNER/PromptoDYS.git
```

### 2. Créer une branche

```bash
# Mettre à jour main
git checkout main
git pull upstream main

# Créer une branche feature
git checkout -b feature/ma-super-feature
# OU pour un bugfix
git checkout -b fix/correction-bug-xyz
# OU pour le build ou la CI
git checkout -b build/windows-release-workflow
# OU pour préparer une livraison : release/v<numéro de version>
git checkout -b release/v1.3.0b1
```

### 3. Développer

```bash
# Installer l'environnement de dev
uv sync --locked   # crée .venv à partir de uv.lock, sans le modifier

# Développer votre feature
# ... modifier les fichiers ...

# Vérifier et tester vos changements
uv run ruff check --fix  # lint, corrige ce qui est sûr (voir Standards de code)
uv run ruff format       # formatage, après le lint (voir Standards de code)
uv run lint-imports      # dépendances entre couches (voir Standards de code)
uv run pyright           # types du paquet promptodys/ (voir Standards de code)
uv run pytest            # tests automatisés (voir Tests)
uv run python askGeminiPrompto.py   # ou : uv run python -m promptodys

# Si vous modifiez les dépendances :
uv add <paquet>
# puis committez pyproject.toml ET uv.lock
```

#### Quelle commande uv utiliser ?

| Situation | Commande |
|---|---|
| Je viens de cloner, ou de faire un `git pull` | `uv sync --locked` |
| Je modifie les dépendances | `uv add <paquet>` / `uv remove <paquet>`, ou `uv sync` après avoir édité `pyproject.toml` |
| Je mets à jour une dépendance | `uv lock --upgrade-package <paquet>` puis `uv sync` |
| Je lance l'application | `uv run python askGeminiPrompto.py` (ou `uv run python -m promptodys`) |
| Je vérifie le code (lint) | `uv run ruff check` |
| Je formate le code (après le lint) | `uv run ruff format` |
| Je vérifie les dépendances entre couches | `uv run lint-imports` |
| Je vérifie les types | `uv run pyright` |
| Je lance les tests | `uv run pytest` |
| Je build l'exécutable (pour le système courant) | `uv sync --locked` puis `uv run pyinstaller --clean PromptoDYS.spec` |
| Je change la version du projet | `uv version 1.3.0b1` (met à jour `pyproject.toml` et `uv.lock` ensemble) |

`--locked` installe exactement ce que contient `uv.lock` et s'arrête en erreur si le fichier ne correspond plus à `pyproject.toml`, au lieu de le modifier en silence. Sans `--locked`, `uv sync` met `uv.lock` à jour : à n'utiliser que lorsque c'est vous qui changez les dépendances, puis committez `pyproject.toml` ET `uv.lock` ensemble.

`uv run` synchronise l'environnement automatiquement avant de lancer la commande : pas besoin d'activer le `.venv` (`source .venv/bin/activate`).

À chaque push, sur n'importe quelle branche, le workflow [ci.yml](.github/workflows/ci.yml) relance ruff (lint et formatage), import-linter, pyright, pytest et le build de l'exécutable Windows. Le résultat s'affiche à côté du commit (✅ ou ❌) et dans l'onglet Actions, avec un résumé en haut de chaque exécution (signalements ruff par règle, tests en échec, résultat du build). Depuis le terminal : `gh run list --workflow ci.yml --branch <branche>`, et `gh run view --log-failed` pour les journaux des étapes en échec.

### 4. Commiter

```bash
# Suivre la convention de commits (voir ci-dessous)
git add .
git commit -m "feat: ajouter support export DOCX"
```

### 5. Pousser et créer la PR

```bash
# Pousser vers votre fork
git push origin feature/ma-super-feature

# Créer la Pull Request via GitHub UI
```

### 6. Checklist PR

Avant de soumettre votre PR, vérifiez :

- [ ] Le code suit les [standards de code](#standards-de-code) : `uv run ruff check --fix` puis `uv run ruff format` ont été lancés, et `uv run ruff check` ne signale rien de nouveau
- [ ] `uv run lint-imports` respecte tous les contrats
- [ ] `uv run pyright` ne signale aucune erreur
- [ ] `uv run pytest` passe, et une correction de bug testable est accompagnée d'un test
- [ ] Le workflow CI est vert sur la branche (onglet Actions)
- [ ] La documentation est mise à jour
- [ ] Le changement est décrit dans la section `[Non publié]` de [CHANGELOG.md](CHANGELOG.md), s'il est notable pour l'utilisateur ou le contributeur
- [ ] Les commits suivent la [structure des commits](#structure-des-commits)
- [ ] Pas de fichiers sensibles (clés API, etc.)
- [ ] Le code est commenté pour les parties complexes

### Publier une version

La numérotation suit le sens de SemVer (MAJEUR.MINEUR.CORRECTIF), écrite au format Python (PEP 440) :

| Version | `pyproject.toml` | Tag git |
|---|---|---|
| Beta | `1.3.0b1`, `1.3.0b2`... | `v1.3.0b1` |
| Release candidate | `1.3.0rc1` | `v1.3.0rc1` |
| Finale | `1.3.0` | `v1.3.0` |

Chaque livraison se prépare sur une branche `release/v<numéro de version>`, créée depuis `master` :

```bash
# 1. Créer la branche de livraison
git checkout master
git pull
git checkout -b release/v1.3.0b1

# 2. Changer la version (pyproject.toml et uv.lock ensemble, ne pas éditer à la main)
uv version 1.3.0b1
#    puis reporter le numéro à la main dans le badge de version du README.md

# 3. Dans CHANGELOG.md, déplacer le contenu de [Non publié] dans une section [1.3.0b1] - AAAA-MM-JJ

# 4. Commiter
git commit -am "build(release): Bump version to 1.3.0b1"

# 5. Poser le tag sur la branche de livraison et le pousser : il déclenche le workflow.
#    Attendre qu'il soit vert dans l'onglet Actions, et vérifier la Release publiée.
git tag v1.3.0b1
git push origin v1.3.0b1

# 6. Une fois la Release validée, fusionner dans master
#    (--no-ff : toujours un commit de merge explicite)
git checkout master
git merge --no-ff release/v1.3.0b1
git push origin master

# 7. Supprimer la branche de livraison locale (-d refuse si elle n'a pas été fusionnée)
git branch -d release/v1.3.0b1
```

`master` ne reçoit ainsi que des versions dont le build et la Release ont réussi. Après la fusion, le commit tagué fait partie de l'historique de `master`.

**Si le workflow échoue**, corriger sur la branche de livraison, dans cet ordre :
1. supprimer la Release si elle a été créée (onglet Releases, icône de suppression). Si on supprime le tag d'abord, la Release reste, détachée de tout tag ;
2. supprimer le tag : `git push --delete origin v1.3.0b1` puis `git tag -d v1.3.0b1` ;
3. corriger, commiter sur `release/v1.3.0b1`, puis reposer et pousser le tag (étape 5).

Seul le tag déclenche le build : pousser la branche `release/...` ne lance rien. Le tag déclenche le workflow [release-windows.yml](.github/workflows/release-windows.yml), qui enchaîne deux jobs :
1. **`build`** (runner Windows, jeton en lecture seule) : vérifie que le tag correspond à la version de `pyproject.toml` et s'arrête en erreur sinon, builde l'exécutable, puis envoie `PromptoDYS.exe`, `GeminiKey.txt.template` et `LISEZMOI.txt` comme artefact ;
2. **`release`** (runner Linux, seulement sur un tag et si `build` a réussi) : récupère l'artefact, le zippe et publie la Release « PromptoDYS v1.3.0b1 » avec `PromptoDYS-v1.3.0b1.zip`, via `gh release create`.

Une beta ou une rc est marquée « Pre-release » automatiquement, et n'est jamais affichée comme dernière version stable.

**Règle de sécurité si vous modifiez le workflow :** `release` est le seul job qui reçoit `contents: write`, et il ne récupère ni n'exécute le code du dépôt. Ne jamais donner le droit d'écriture à un job qui fait un checkout, installe les dépendances ou lance le build : une dépendance compromise pourrait alors pousser du code ou des tags avec le jeton.

---

## 📐 Standards de code

### Python (PEP 8)

```python
# ✅ BON
def traitement_gemini():
    """Traitement IA Gemini : lecture → prompt → stream → injection."""
    client = init_gemini_client()
    if not client:
        log_message("❌ ÉCHEC: Impossible d'initialiser Gemini")
        return

    # ... reste du code ...


# ❌ MAUVAIS
def TraitementGemini():
    client=init_gemini_client()
    if not client:return
```

### Lint avec ruff

[Ruff](https://docs.astral.sh/ruff/) vérifie le code sans l'exécuter. Il est installé avec les dépendances de dev (`uv sync --locked`) et configuré dans `pyproject.toml` (sections `[tool.ruff]`), pour que tout le monde obtienne le même résultat :

| Règles | Ce qu'elles détectent |
|---|---|
| `F` | Erreurs : noms non définis, imports inutilisés |
| `E`, `W` | Style PEP 8 (pycodestyle) |
| `B` | Bugs probables (flake8-bugbear) |
| `UP` | Syntaxe Python à moderniser |
| `SIM` | Code simplifiable |

```bash
uv run ruff check         # signale les problèmes
uv run ruff check --fix   # corrige automatiquement ceux qui sont sûrs
```

### Formatage avec ruff

`ruff format` met en forme le code (guillemets doubles, espaces, retours à la ligne, virgules finales) pour que tout le monde écrive de la même façon. Il formate aussi les blocs de code Python des fichiers Markdown, sauf ce fichier-ci : l'exemple « ❌ MAUVAIS » ci-dessus doit rester mal formaté (exclusion dans `[tool.ruff.format]`).

```bash
uv run ruff format          # formate le code, après ruff check --fix, avant de commiter
uv run ruff format --check  # vérifie sans modifier (ce que fait la CI)
```

Lancez-le après `ruff check --fix` : les corrections automatiques du lint (import retiré, syntaxe modernisée) peuvent laisser du code à reformater.

La CI échoue si un fichier n'est pas formaté.

Quelques signalements anciens restent à traiter (`except:` nus, espaces sur des lignes vides) : n'en ajoutez pas de nouveaux. Faites les corrections de lint dans un commit à part, jamais dans le même commit qu'une correction de bug.

### Dépendances entre couches avec import-linter

Le paquet `promptodys/` est découpé en trois couches : `domain` (règles métier et cas d'usage), `infrastructure` (Gemini, Eel, disque, PDF) et `presentation` (panneau Tkinter). La règle de dépendance est `presentation → domain ← infrastructure` : le domaine n'importe ni les autres couches, ni Tk, Eel, Gemini ou reportlab, et la présentation n'importe pas l'infrastructure. Seul le module d'assemblage `promptodys/app.py` (fonction `main()`) relie les couches, et aucune couche ne l'importe. Quand la présentation a besoin d'un service technique (ouvrir la fenêtre de l'éditeur, lancer le traitement), elle déclare ce qu'elle attend, comme le `Protocol` `EditorWindow` ou un paramètre `Callable`, et `main()` lui passe l'implémentation.

[import-linter](https://import-linter.readthedocs.io/) vérifie cette règle à partir des contrats de la section `[tool.importlinter]` de `pyproject.toml` :

```bash
uv run lint-imports   # signale chaque import qui rompt un contrat
```

La CI échoue si un contrat est rompu. Si vous en rencontrez un, déplacez le code dans la bonne couche ou passez par un port (`Protocol`) du domaine, plutôt que de modifier le contrat.

### Vérification des types avec pyright

[pyright](https://microsoft.github.io/pyright/) vérifie les annotations de type sans exécuter le code. Il est installé avec les dépendances de dev et configuré dans la section `[tool.pyright]` de `pyproject.toml` :

| Périmètre | Mode | Pourquoi |
|---|---|---|
| `promptodys/domain/` | `strict` | Code entièrement annoté, sans bibliothèque tierce : chaque paramètre, retour et conteneur doit avoir un type connu |
| reste de `promptodys/` | `standard` | Les couches infrastructure et présentation dépendent de bibliothèques mal typées (Eel, google-genai) |
| `askGeminiPrompto.py`, `tests/` | non vérifiés | `askGeminiPrompto.py` n'est plus qu'une enveloppe de `promptodys.app.main()` ; les tests ne sont pas annotés |

```bash
uv run pyright   # signale les erreurs de type du paquet promptodys/
```

Lancez-le toujours par `uv run` : uv active `.venv`, où pyright trouve l'interpréteur (Python 3.14) et les bibliothèques du projet. La CI échoue si pyright signale une erreur.

En mode strict, les conteneurs vides doivent porter leur type : `field(default_factory=list[Image])` et non `field(default_factory=list)`, `step_logs: list[str] = []` et non `step_logs = []`.

### Règles générales

1. **Indentation** : 4 espaces (pas de tabs)
2. **Longueur de ligne** : Maximum 120 caractères (vérifié par ruff)
3. **Noms de variables** : `snake_case` pour Python, `camelCase` pour JavaScript
4. **Noms de fonctions** : Descriptifs ; en anglais dans le paquet `promptodys/` (modules, classes, fonctions, attributs), messages, docstrings et commentaires en français
5. **Commentaires** : Expliquer le "pourquoi", pas le "quoi"
6. **Logs** : utiliser le module `logging` avec un logger privé au module, `_logger = logging.getLogger(__name__)`, et des préfixes à emojis pour la lisibilité : `main()` les renvoie vers la console et le rapport. `log_message()`, provisoire, ne sert plus que dans `promptodys/app.py`, jusqu'à R7
7. **Imports du paquet** : importer le module, pas ses fonctions : `from promptodys.domain import note`, puis `note.extract_note_content(...)`. L'appel montre d'où vient la fonction, et un test peut la remplacer avec `monkeypatch.setattr(note, ...)`. Seuls les tests d'un module importent directement les fonctions qu'ils testent
8. **Noms privés** : préfixer par `_` ce qui ne sert qu'au module (`_logger`, regex compilées comme `_BOLD_MARKER_PATTERN`). Une regex compilée porte le suffixe `_PATTERN`
9. **Ports du domaine** : un adaptateur hérite explicitement du `Protocol` qu'il implémente (`class EelEditor(ports.Editor)`). Les faux des tests n'en héritent pas : une méthode manquante y lève `AttributeError` dès son appel

### Structure des logs

```python
# Format standard
_logger.info("🔧 ÉTAPE: Description de l'étape...")
_logger.info("✅ SUCCÈS: Opération réussie")
_logger.info("❌ ÉCHEC: Erreur détectée")
_logger.info("⚠️ ATTENTION: Avertissement important")
_logger.info("💡 INFO: Information complémentaire")
```

---

## 📝 Structure des commits

Nous utilisons la convention [Conventional Commits](https://www.conventionalcommits.org/).

### Format

```
<type>(<scope>): <description>

[corps optionnel]

[footer optionnel]
```

### Types de commits

| Type | Description | Exemple |
|------|-------------|---------|
| `feat` | Nouvelle fonctionnalité | `feat: ajouter export DOCX` |
| `fix` | Correction de bug | `fix: corriger crash au démarrage` |
| `docs` | Documentation uniquement | `docs: améliorer README installation` |
| `style` | Formatage, sans changement de code | `style: formater selon PEP 8` |
| `refactor` | Refactorisation du code | `refactor: extraire fonction PDF` |
| `perf` | Amélioration de performance | `perf: optimiser streaming Gemini` |
| `test` | Ajout de tests | `test: ajouter tests unitaires` |
| `build` | Build, CI, livraison | `build(ci): ajouter le workflow de release Windows` |
| `chore` | Maintenance | `chore: mettre à jour dépendances` |

### Exemples

```bash
# Feature
git commit -m "feat(pdf): ajouter support images dans PDF"

# Fix
git commit -m "fix(gemini): gérer timeout API"

# Documentation
git commit -m "docs(readme): ajouter section troubleshooting"

# Breaking change
git commit -m "feat(api)!: changer format de config

BREAKING CHANGE: Le fichier config.yaml a un nouveau format.
Voir migration guide dans docs/MIGRATION.md"
```

---

## 🧪 Tests

Les tests automatisés utilisent [pytest](https://docs.pytest.org/), installé avec les dépendances de dev. Ils sont dans le dossier `tests/` et se lancent sans réseau. Seuls les tests du panneau (`tests/presentation/`) ont besoin d'un écran : ils créent des fenêtres Tk cachées, et sont sautés si aucun écran n'est disponible :

```bash
uv run pytest
```

| Fichier | Ce qu'il couvre |
|---|---|
| `domain/test_note.py` | Prompt, extraction de la note corrigée et du débrief, ajout de la note d'origine, marqueurs `__BOLD_n__` |
| `domain/test_report.py` | Contenu Markdown du rapport |
| `domain/test_documents.py` | Chemin de sauvegarde (assainissement du nom, anti-récursion), cas d'usage sauvegarder et ouvrir |
| `domain/test_processing.py` | Cas d'usage du traitement IA : succès, abandon, erreurs de l'IA |
| `domain/conftest.py` | Faux éditeur, faux modèle d'IA et faux rangement, partagés par les tests du domaine |
| `infrastructure/test_config.py` | Chemins, clé API, modèle de prompt, dossier de l'éditeur |
| `infrastructure/test_disk_document_store.py` | Rangement des documents sur un vrai disque (dossier temporaire) |
| `infrastructure/test_eel_editor.py` | Adaptateur `EelEditor` et `EelWindow` (Eel simulé), événements de React, port du serveur |
| `infrastructure/test_gemini_model.py` | Adaptateur `GeminiModel` (Gemini simulé) |
| `infrastructure/test_pdf_report.py` | Rapport PDF ReportLab |
| `presentation/test_control_panel.py` | Panneau de contrôle (fenêtre cachée) : état de l'éditeur, double clic, abandon du traitement, fermeture, avec éditeur, fenêtre et traitement simulés |
| `test_app.py` | Assemblage du traitement IA, `run_processing()` (étapes, rapport, abandon) avec Gemini, l'éditeur et le PDF simulés |
| `test_import.py` | Importer `askGeminiPrompto.py`, une couche ou le module d'assemblage ne crée aucun dossier (ni fenêtre, pour la présentation) |
| `test_logs.py` | Les logs du paquet arrivent dans la console et le rapport |

`pyproject.toml` (section `[tool.pytest.ini_options]`) rend `askGeminiPrompto.py` et le paquet `promptodys/` importables depuis `tests/`, et pytest-timeout fait échouer au bout de 10 s un test qui boucle, au lieu de figer pytest.

Pour être testable, une fonction doit pouvoir être appelée sans interface, sans réseau et sans écrire sur le disque : placez la logique dans la couche domaine, sous forme de fonction pure comme `documents.prepare_save_path()`, ou de cas d'usage qui reçoit ses dépendances par les ports, comme `processing.process_note()`. Les tests lui passent alors de faux adaptateurs.

**Tests à implémenter :**
- [ ] Tests d'intégration pour le pipeline IA
- [ ] Tests end-to-end pour l'interface Eel
- [ ] Tests de génération PDF

---

## 💬 Questions ?

Si vous avez des questions sur le processus de contribution :

1. Consultez la [documentation existante](README.md)
2. Cherchez dans les [Issues](https://github.com/lecinquiemejour-code/PromptoDYS_app/issues)
3. Créez une nouvelle issue avec le label `question`

---

## 🙏 Merci !

Votre contribution, quelle que soit sa taille, fait progresser le projet et aide les élèves DYS. Merci de prendre le temps de contribuer ! ❤️

---

**Dernière mise à jour :** 30/10/2026
