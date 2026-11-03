"""Configuration de l'application : modèle Gemini, chemins, port de l'éditeur, clé API.

Ce module ne fait que calculer des valeurs : aucun dossier n'est créé à l'import (constat M12),
main() s'en charge au démarrage.
"""

import logging
import os
import sys

from google.genai import types

from promptodys.domain import note

_logger = logging.getLogger(__name__)

# Modèle Gemini utilisé (ex. "gemini-3.8-flash", "gemini-3.5-flash-lite")
GEMINI_MODEL = "gemini-3.8-flash"

# Niveau de réflexion Gemini 3.x
GEMINI_THINKING_LEVEL = types.ThinkingLevel.LOW

# Dossier de l'application : celui de l'exe une fois packagé, la racine du dépôt en développement
# (promptodys/infrastructure/config.py → trois niveaux plus haut).
# GeminiKey.txt et reports/ y sont lus et écrits, quel que soit le dossier courant.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTS_DIR = os.path.join(APP_DIR, "reports")

# Ressources livrées avec l'application : copie embarquée dans l'exe (sys._MEIPASS, dossier où
# PyInstaller les décompresse), racine du dépôt en développement. Un fichier posé à côté de l'exe est ignoré.
RESOURCES_DIR: str = getattr(sys, "_MEIPASS", None) or APP_DIR
PROMPT_TEMPLATE_FILE = os.path.join(RESOURCES_DIR, "promptodys.prompt")

# Port du serveur Eel. Il reste fixe : le localStorage et l'IndexedDB de Chrome
# (thème, brouillon, images) sont rattachés à l'origine http://localhost:<port>
EEL_PORT = 8080

GEMINI_API_KEY_FILE = os.path.join(APP_DIR, "GeminiKey.txt")
GEMINI_API_KEY_PLACEHOLDER = "YOUR_GEMINI_API_KEY_HERE"


def read_api_key() -> str:
    """Lit la clé API dans GeminiKey.txt (ignore lignes vides et commentaires #).
    Lève FileNotFoundError si le fichier est absent."""
    # utf-8-sig : tolère le BOM ajouté par le Bloc-notes Windows
    with open(GEMINI_API_KEY_FILE, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return ""


def read_prompt_template() -> str | None:
    """Lit le modèle de prompt promptodys.prompt (copie embarquée dans l'exe, ou celle du dépôt).
    None s'il est absent, illisible ou sans balise [TEXTE]"""
    try:
        with open(PROMPT_TEMPLATE_FILE, encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        _logger.info("❌ ÉCHEC: Fichier promptodys.prompt introuvable")
        return None
    except Exception as e:
        _logger.info(f"❌ ÉCHEC: Erreur lecture promptodys.prompt: {e}")
        return None

    if note.TEXT_PLACEHOLDER not in template:
        _logger.info(f"❌ ÉCHEC: Balise {note.TEXT_PLACEHOLDER} manquante dans promptodys.prompt")
        return None
    return template


def find_web_folder() -> str | None:
    """Trouve le dossier contenant index.html (compatible PyInstaller)"""
    meipass: str | None = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        # Exécutable PyInstaller : ressources embarquées
        base_path = meipass
        possible_folders = ["build_web", "build"]
    else:
        # Mode développement normal
        base_path = APP_DIR
        possible_folders = ["build_web", "build", "dist", "public", "."]

    for folder in possible_folders:
        index_path = os.path.join(base_path, folder, "index.html")
        if os.path.exists(index_path):
            print(f"✅ Dossier web trouvé: {folder}/")
            return os.path.join(base_path, folder)

    print("⌐ Aucun index.html trouvé dans:", possible_folders)
    return None


# --- Répertoire par défaut des projets PromptoDYS ---
def _get_documents_folder() -> str:
    """Récupère le vrai dossier Documents Windows (compatible OneDrive)"""
    try:
        import ctypes
        import ctypes.wintypes

        CSIDL_PERSONAL = 5  # "Mes documents" dans l'API Shell Windows
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf)  # type: ignore[attr-defined]
        if buf.value:
            return buf.value
    except Exception:
        pass
    # Fallback si non-Windows ou erreur
    return os.path.expanduser("~/Documents")


PROMPTO_DOCS_DIR = os.path.join(_get_documents_folder(), "PromptoDYS")


# --- Profil Chrome dédié à l'éditeur ---
def _get_chrome_profile_dir() -> str:
    """Dossier du profil Chrome isolé de PromptoDYS (hors Documents, non synchronisé par OneDrive)"""
    if sys.platform == "win32":
        base_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base_dir = os.path.expanduser("~/Library/Application Support")
    else:
        # Fallback Linux et autres
        base_dir = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base_dir, "PromptoDYS", "ChromeProfile")


CHROME_PROFILE_DIR = _get_chrome_profile_dir()
