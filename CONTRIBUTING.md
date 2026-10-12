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
```

### 3. Développer

```bash
# Installer l'environnement de dev
uv sync   # crée .venv à partir de uv.lock

# Développer votre feature
# ... modifier les fichiers ...

# Tester vos changements
uv run python askGeminiPrompto.py

# Si vous modifiez les dépendances : 
uv add <paquet>
# puis committez pyproject.toml ET uv.lock
```

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
| `chore` | Maintenance, build, etc. | `chore: mettre à jour dépendances` |

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
