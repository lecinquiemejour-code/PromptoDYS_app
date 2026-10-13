# ⚠️ ANTIVIRUS : FAUX POSITIF POSSIBLE

## 🛡️ Pourquoi mon antivirus détecte PromptoDYS ?

**PromptoDYS.exe** peut être signalé par certains antivirus comme "suspect" ou "potentiellement dangereux". Ceci est un **FAUX POSITIF** causé par :

1. **PyInstaller** : L'outil utilisé pour créer l'exécutable compresse et empaquette Python, ce qui peut ressembler à un comportement de malware pour certains antivirus.
2. **Absence de signature numérique** : Les certificats de signature de code coûtent plusieurs centaines d'euros par an. Ce projet open-source n'en possède pas.
3. **Exécutable récent** : Les nouveaux .exe ne sont pas encore dans les bases de données antivirus.

---

## ✅ COMMENT VÉRIFIER L'INTÉGRITÉ DU FICHIER

### Méthode 1 : Vérification par hash SHA256

Chaque version de PromptoDYS possède un hash SHA256 unique qui garantit son intégrité :

**Version 1.2.0 - Hash SHA256 :**
```
c910ada541813ca2d46588c6bf789df364fa78f4ee2173d8badc54fa02ad1dfc
```

**Comment vérifier sur Windows :**
```powershell
# Ouvrir PowerShell dans le dossier contenant PromptoDYS.exe
certutil -hashfile PromptoDYS.exe SHA256
```

Le hash affiché doit correspondre EXACTEMENT au hash ci-dessus.

### Méthode 2 : Rapport VirusTotal

Consultez le rapport VirusTotal complet pour cette version :
- **Lien VirusTotal** : [À ajouter après build]

VirusTotal analyse le fichier avec 70+ antivirus. La plupart le marqueront comme **sûr**.

---

## 🔧 SOLUTIONS POUR UTILISER PROMPTODYS

### Solution 1 : Ajouter une exception dans Windows Defender

1. Ouvrir **Paramètres Windows** (touche Windows + I)
2. Aller dans **Confidentialité et sécurité** → **Sécurité Windows**
3. Cliquer sur **Protection contre les virus et menaces**
4. Sous "Paramètres de protection contre les virus et menaces", cliquer sur **Gérer les paramètres**
5. Faire défiler jusqu'à **Exclusions**
6. Cliquer sur **Ajouter ou supprimer des exclusions**
7. Cliquer sur **Ajouter une exclusion** → **Fichier**
8. Sélectionner **PromptoDYS.exe**

### Solution 2 : Autoriser temporairement

Lors du premier lancement, Windows peut afficher "Application non reconnue" :
1. Cliquer sur **Informations complémentaires**
2. Cliquer sur **Exécuter quand même**

### Solution 3 : Utiliser le code source (pour utilisateurs avancés)

Si vous préférez ne pas utiliser l'exécutable :
```bash
# Cloner le dépôt
git clone https://github.com/lecinquiemejour-code/PromptoDYS_app.git
cd PromptoDYS_app

# Installer les dépendances (nécessite uv : https://docs.astral.sh/uv/)
uv sync --locked

# Lancer directement le script Python
uv run python askGeminiPrompto.py
```

---

## 📊 TRANSPARENCE TOTALE

PromptoDYS est un projet **open-source** sous licence **GPL v3** :
- ✅ Le code source complet est disponible sur GitHub
- ✅ Aucune collecte de données
- ✅ Aucune connexion sortante (sauf vers l'API Google Gemini avec VOTRE clé)
- ✅ Toutes les données restent sur VOTRE machine

**Dépôt GitHub** : https://github.com/lecinquiemejour-code/PromptoDYS_app

---

## 🆘 BESOIN D'AIDE ?

Si vous avez des questions ou des problèmes :
- 📧 Ouvrir une [issue sur GitHub](https://github.com/lecinquiemejour-code/PromptoDYS_app/issues)
- 💬 Contacter le développeur

---

**Fait avec ❤️ pour aider les élèves DYS**
