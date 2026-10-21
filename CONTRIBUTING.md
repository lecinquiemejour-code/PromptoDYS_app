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

# Tester vos changements
uv run python askGeminiPrompto.py

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
| Je lance l'application | `uv run python askGeminiPrompto.py` |
| Je build l'exécutable (pour le système courant) | `uv sync --locked` puis `uv run pyinstaller --clean PromptoDYS.spec` |
| Je change la version du projet | `uv version 1.3.0b1` (met à jour `pyproject.toml` et `uv.lock` ensemble) |

`--locked` installe exactement ce que contient `uv.lock` et s'arrête en erreur si le fichier ne correspond plus à `pyproject.toml`, au lieu de le modifier en silence. Sans `--locked`, `uv sync` met `uv.lock` à jour : à n'utiliser que lorsque c'est vous qui changez les dépendances, puis committez `pyproject.toml` ET `uv.lock` ensemble.

`uv run` synchronise l'environnement automatiquement avant de lancer la commande : pas besoin d'activer le `.venv` (`source .venv/bin/activate`).

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

- [ ] Le code suit les [standards de code](#standards-de-code)
- [ ] Les tests passent (si applicable)
- [ ] La documentation est mise à jour
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
1. **`build`** (runner Windows, jeton en lecture seule) : vérifie que le tag correspond à la version de `pyproject.toml` et s'arrête en erreur sinon, builde l'exécutable, puis envoie `PromptoDYS.exe` et `.env.template` comme artefact ;
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

### Règles générales

1. **Indentation** : 4 espaces (pas de tabs)
2. **Longueur de ligne** : Maximum 100 caractères
3. **Noms de variables** : `snake_case` pour Python, `camelCase` pour JavaScript
4. **Noms de fonctions** : Descriptifs et en français (cohérence avec le projet)
5. **Commentaires** : Expliquer le "pourquoi", pas le "quoi"
6. **Logs** : Utiliser `log_message()` avec emojis pour la lisibilité

### Structure des logs

```python
# Format standard
log_message("🔧 ÉTAPE: Description de l'étape...")
log_message("✅ SUCCÈS: Opération réussie")
log_message("❌ ÉCHEC: Erreur détectée")
log_message("⚠️ ATTENTION: Avertissement important")
log_message("💡 INFO: Information complémentaire")
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

## 🧪 Tests (à venir)

Pour l'instant, le projet n'a pas de suite de tests automatisés. C'est une excellente opportunité de contribution !

**Tests à implémenter :**
- [ ] Tests unitaires pour les fonctions de parsing Markdown
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

**Dernière mise à jour :** 08/01/2026
