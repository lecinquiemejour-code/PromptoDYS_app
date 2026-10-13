# 🚀 Procédure de Build PromptoDYS v1.2.0

> **⚠️ Document historique, ne plus suivre.** Le problème décrit ci-dessous concernait Python 3.10.0. Le projet utilise désormais Python 3.14, fourni par uv, et les dépendances sont gérées par `pyproject.toml` et `uv.lock` : les commandes `python -m venv` et `pip install` de ce document ne s'appliquent plus.
> La procédure de build à jour est dans le [README](README.md#-build-exécutable-windows) : `uv sync --locked` puis `uv run pyinstaller --clean PromptoDYS.spec`.

## ⚠️ Problème Technique Détecté

**Erreur** : `IndexError: tuple index out of range` lors du build PyInstaller

**Cause** : Bug connu de Python 3.10.0 avec le module `dis` utilisé par PyInstaller. Ce problème affecte toutes les versions de PyInstaller avec Python 3.10.0 spécifiquement.

---

## ✅ SOLUTIONS POSSIBLES

### Solution 1 : Mise à jour de Python (RECOMMANDÉ) ⭐

**Installer Python 3.10.11 ou supérieur** (corrige le bug `dis`)

1. Télécharger Python 3.10.11 depuis https://www.python.org/downloads/
2. Installer la nouvelle version
3. Recréer l'environnement virtuel :
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install eel google-genai reportlab markdown pyinstaller
   ```
4. Lancer le build :
   ```powershell
   pyinstaller --clean PromptoDYS.spec
   ```

---

### Solution 2 : Build sans environnement virtuel

Tenter le build en dehors de `.venv` :

```powershell
# Désactiver l'environnement virtuel si actif
deactivate

# Installer PyInstaller globalement
pip install --user pyinstaller==6.11.1

# Lancer le build
pyinstaller --clean PromptoDYS.spec
```

---

### Solution 3 : Build manuel avec cx_Freeze (Alternative à PyInstaller)

Utiliser cx_Freeze au lieu de PyInstaller :

1. Installer cx_Freeze :
   ```powershell
   pip install cx_Freeze
   ```

2. Créer un fichier `setup.py` :
   ```python
   from cx_Freeze import setup, Executable
   
   setup(
       name="PromptoDYS",
       version="1.2.0",
       description="Assistant IA pour élèves DYS",
       executables=[Executable("askGeminiPrompto.py", base="Win32GUI")],
       options={
           "build_exe": {
               "packages": ["eel", "google.genai", "reportlab", "markdown"],
               "include_files": [
                   ("build_web", "build_web"),
                   ("prompto.dys", "prompto.dys"),
                   ("GeminiKey.txt", "GeminiKey.txt")
               ]
           }
       }
   )
   ```

3. Lancer le build :
   ```powershell
   python setup.py build
   ```

---

## 📋 ÉTAT ACTUEL DU BUILD

### ✅ Complété
- [x] Mise à jour version 1.2.0 (README, CHANGELOG, code Python)
- [x] Création `version_info.txt` (métadonnées Windows)
- [x] Modification `PromptoDYS.spec` (UPX désactivé, console=False)
- [x] Création `README_ANTIVIRUS.md`

### ⏸️ En attente
- [ ] Build réussi de l'exécutable
- [ ] Génération hash SHA256
- [ ] Test de l'exécutable
- [ ] Mise à jour du PDF de procédure

---

## 🔧 PROCHAINES ÉTAPES

**Choix à faire** :
1. Mettre à jour Python vers 3.10.11+ (meilleure solution)
2. Essayer Solution 2 ou 3
3. Continuer avec les fichiers préparés (tout est prêt) une fois Python mis à jour

---

**Note** : Tous les fichiers de configuration anti-antivirus sont prêts. Une fois Python mis à jour, le build devrait fonctionner immédiatement avec `pyinstaller --clean PromptoDYS.spec`.
