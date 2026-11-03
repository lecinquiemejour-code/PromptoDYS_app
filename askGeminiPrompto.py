#!/usr/bin/env python3
"""
Script Python unifié pour l'éditeur Markdown avec intégration Eel + IA Gemini
Combinaison : Interface desktop + Assistant IA pour traitement de texte

GUI de contrôle avec Tkinter + sv_ttk (thème Sun Valley Windows 11)

Installation requise (dépendances déclarées dans pyproject.toml):
uv sync --locked
Usage:
uv run python askGeminiPrompto.py

Fichiers requis:
- GeminiKey.txt (clé API Gemini)
- promptodys.prompt (template de traitement IA)
- build/index.html (interface web)

Fonctionnalités:
- Sauvegarde automatique des rapports en PDF uniquement
- Rendu Markdown professionnel dans les PDF avec reportlab
- Interface console simple et efficace
- Dossier reports/ créé automatiquement
- CAPTURE COMPLÈTE de tous les logs dans les rapports
"""

import contextlib
import eel
import logging
import os
import sys
import threading
import time
import socket
from datetime import datetime
import re
import base64
import mimetypes
# import socket # Supprimé : Vérification internet retirée

# --- Imports pour PDF avec reportlab (remplace weasyprint) ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# --- Imports Gemini ---
from google import genai
from google.genai import types
import google.genai.errors as genai_errors

# --- Imports GUI Tkinter + sv_ttk ---
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sv_ttk  # Thème Sun Valley (Windows 11 look)
import subprocess  # Pour ouvrir le dossier reports

# --- Couche domaine (règles pures, voir promptodys/) ---
from promptodys.domain import documents, note, ports, processing, report

# Modèle Gemini utilisé (ex. "gemini-3.8-flash", "gemini-3.5-flash-lite")
GEMINI_MODEL = "gemini-3.8-flash"

# Niveau de réflexion Gemini 3.x
GEMINI_THINKING_LEVEL = types.ThinkingLevel.LOW

# Dossier de l'application : celui de l'exe une fois packagé, celui du script en développement.
# GeminiKey.txt et reports/ y sont lus et écrits, quel que soit le dossier courant.
APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
REPORTS_DIR = os.path.join(APP_DIR, "reports")

# Port du serveur Eel. Il reste fixe : le localStorage et l'IndexedDB de Chrome
# (thème, brouillon, images) sont rattachés à l'origine http://localhost:<port>
EEL_PORT = 8080

# --- NOUVELLE VARIABLE POUR CAPTURER TOUS LES LOGS ---
logs_complets = []

# --- ÉTAT DU TRAITEMENT IA ---
# Jeton d'annulation (threading.Event) du traitement IA en cours, None si aucun traitement en cours
annulation_en_cours = None

# --- VARIABLE POUR TRACKING TEMPOREL DE L'ÉDITEUR ---
last_editor_activity = None  # Timestamp de la dernière activité éditeur détectée

# --- CHEMIN DU DOCUMENT COURANT (style Arduino : mémorise le dernier save/open) ---
current_document_path = None  # Ex: "C:/.../PromptoDYS/MonDoc" → sauvegarde directe au prochain Ctrl+S


# Classe pour rediriger stdout vers la GUI
# Classe pour rediriger stdout/stderr vers la GUI tout en gardant la console
class RedirectText:
    def __init__(self, text_widget_updater, is_stderr=False):
        self.updater = text_widget_updater
        self.is_stderr = is_stderr
        # On garde une référence vers le VRAI stdout/stderr d'origine
        if is_stderr:
            self.terminal = sys.__stderr__
        else:
            self.terminal = sys.__stdout__

    def write(self, message):
        # Écrire dans la console réelle (si disponible)
        if self.terminal:
            with contextlib.suppress(Exception):
                self.terminal.write(message)
                self.terminal.flush()

        # Mettre à jour la GUI (éviter de planter si la GUI est fermée)
        with contextlib.suppress(Exception):
            self.updater(message)

    def flush(self):
        if self.terminal:
            with contextlib.suppress(Exception):
                self.terminal.flush()


def log_message(message):
    """Log un message dans la console ET le capture pour les rapports"""
    print(message, flush=True)
    # Les prints sont maintenant redirigés vers la GUI via stdout mais on garde l'ajout explicite aux logs complets
    # Capturer aussi dans les logs complets
    logs_complets.append(message)


class LogMessageHandler(logging.Handler):
    """Pont provisoire : renvoie les logs de la couche domaine vers log_message (console, GUI, rapport).
    Sera remplacé par les vrais handlers de logging avec R7."""

    def emit(self, record):
        with contextlib.suppress(Exception):
            log_message(self.format(record))


def configure_logger():
    """Envoie les logs du paquet promptodys vers log_message, message seul (sans niveau ni heure).
    Appelée par main(), jamais à l'import : les tests gardent la configuration de logging par défaut."""
    logger = logging.getLogger("promptodys")
    logger.setLevel(logging.INFO)
    logger.addHandler(LogMessageHandler())
    logger.propagate = False  # pas de second affichage par le logger racine


def find_web_folder():
    """Trouve le dossier contenant index.html (compatible PyInstaller)"""
    # Si on est dans un exécutable PyInstaller
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
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


def get_markdown():
    """
    📖 LECTURE: Récupère le contenu Markdown actuel
    """
    try:
        content = eel.readMarkdown()()
        print(f"✅ SUCCÈS: Contenu récupéré ({len(content)} caractères)")
        return content
    except Exception as e:
        print(f"❌ ÉCHEC: Erreur lecture: {e}")
        return ""


def afficher_contenu_editeur(contenu, titre="📄 CONTENU DE L'ÉDITEUR"):
    """Affiche le contenu de l'éditeur de manière formatée"""
    print(f"\n{titre}")
    print("=" * 50)
    if contenu.strip():
        print(contenu)
    else:
        print("📝 (Éditeur vide)")
    print("=" * 50)


def set_markdown(markdown_content):
    """
    ✏️ ÉCRITURE: Injecte du contenu Markdown
    """
    try:
        eel.writeMarkdown(markdown_content)
        print(f"✅ SUCCÈS: Contenu injecté ({len(markdown_content)} caractères)")
        return True
    except Exception as e:
        print(f"❌ ÉCHEC: Erreur écriture: {e}")
        return False


# --- Répertoire par défaut des projets PromptoDYS ---
def _get_documents_folder():
    """Récupère le vrai dossier Documents Windows (compatible OneDrive)"""
    try:
        import ctypes
        import ctypes.wintypes

        CSIDL_PERSONAL = 5  # "Mes documents" dans l'API Shell Windows
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf)
        if buf.value:
            return buf.value
    except Exception:
        pass
    # Fallback si non-Windows ou erreur
    return os.path.expanduser("~/Documents")


PROMPTO_DOCS_DIR = os.path.join(_get_documents_folder(), "PromptoDYS")


# --- Profil Chrome dédié à l'éditeur ---
def _get_chrome_profile_dir():
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


# --- Disponibilité du port de l'éditeur ---
def port_libre(port):
    """Vrai si aucun programme n'écoute sur le port et qu'on peut s'y attacher"""
    # Un programme qui répond déjà sur le port : Chrome afficherait sa page à lui
    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            return False
    except OSError:
        pass
    # Le serveur Eel doit pouvoir s'attacher au port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform != "win32":
            # Comme le serveur gevent : ignorer les connexions en TIME_WAIT
            # (sous Windows, SO_REUSEADDR permettrait de voler un port occupé)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("localhost", port))
        except OSError:
            return False
    return True


def attendre_port_libre(port, delai=5.0):
    """Attend que le port se libère, au plus delai secondes (serveur Eel précédent pas encore arrêté)"""
    fin = time.monotonic() + delai
    while not port_libre(port):
        if time.monotonic() >= fin:
            return False
        time.sleep(0.5)
    return True


# --- Adaptateurs des ports du domaine (provisoires : iront dans promptodys/infrastructure/) ---


class EelEditor(ports.Editor):
    """Éditeur React, joint par le pont Eel.
    Les images voyagent en base64 côté JavaScript, en binaire côté domaine."""

    def read_markdown(self):
        contenu = get_markdown()
        afficher_contenu_editeur(contenu, "📄 CONTENU LU DEPUIS L'ÉDITEUR")
        return contenu

    def write_markdown(self, markdown):
        afficher_contenu_editeur(markdown, "📄 CONTENU À INJECTER DANS L'ÉDITEUR")
        return set_markdown(markdown)

    def read_document(self):
        """Document de l'éditeur (texte + images), None si l'éditeur n'a rien renvoyé"""
        print(f"🔍 DEBUG: editeur_lance={editeur_lance}, last_editor_activity={last_editor_activity}")
        print("🔍 DEBUG: Appel eel.readDocumentData()()...")
        try:
            data = eel.readDocumentData()()
            print(f"🔍 DEBUG readDocumentData retour → type={type(data).__name__}")
            if data is None:
                print("🔍 DEBUG readDocumentData → None (la fonction JS retourne undefined ou null)")
            elif isinstance(data, dict):
                print(f"🔍 DEBUG readDocumentData → dict avec clés: {list(data.keys())}")
                if "markdown" in data:
                    print(f"🔍 DEBUG   markdown: {len(data['markdown'])} caractères")
                if "images" in data:
                    print(f"🔍 DEBUG   images: {len(data['images'])} image(s)")
            elif isinstance(data, str):
                print(f"🔍 DEBUG readDocumentData → string ({len(data)} car.): {repr(data)[:200]}")
            elif isinstance(data, bool):
                print(f"🔍 DEBUG readDocumentData → bool: {data}")
            else:
                print(f"🔍 DEBUG readDocumentData → {type(data).__name__}: {repr(data)[:500]}")
        except Exception as e:
            print(f"❌ SAUVEGARDE: Erreur appel readDocumentData: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            return None

        if not data or not isinstance(data, dict):
            print(f"❌ SAUVEGARDE: Aucune donnée exploitable reçue de l'éditeur ({repr(data)[:200]})")
            return None

        print(f"📄 SAUVEGARDE: Markdown reçu ({len(data.get('markdown', ''))} caractères)")
        print(f"🖼️ SAUVEGARDE: {len(data.get('images', []))} image(s) reçue(s)")

        images = []
        for image in data.get("images", []):
            try:
                mime_type = image.get("mimeType") or mimetypes.guess_type(image["filename"])[0] or ""
                images.append(
                    ports.Image(
                        filename=image["filename"], content=base64.b64decode(image["data"]), mime_type=mime_type
                    )
                )
            except Exception as e:
                print(f"  ❌ Erreur image '{image.get('filename')}': {e}")
        return ports.Document(markdown=data.get("markdown", ""), images=images)

    def write_document(self, document):
        """Charge le document dans l'éditeur. Faux si l'appel Eel a échoué"""
        data_to_send = {
            "markdown": document.markdown,
            "images": [
                {
                    "filename": image.filename,
                    "data": base64.b64encode(image.content).decode("utf-8"),
                    "mimeType": image.mime_type,
                }
                for image in document.images
            ],
        }
        nb_car, nb_images = len(data_to_send["markdown"]), len(data_to_send["images"])
        print(f"📤 OUVERTURE: Envoi à l'éditeur ({nb_car} car. + {nb_images} image(s))...")
        print(f"🔍 DEBUG: editeur_lance={editeur_lance}, last_editor_activity={last_editor_activity}")
        print(f"🔍 DEBUG: Appel eel.writeDocumentData() avec {nb_car} car. + {nb_images} image(s)...")
        print(f"🔍 DEBUG: data_to_send → clés={list(data_to_send.keys())}")
        print(f"🔍 DEBUG:   markdown: {nb_car} car., début: {repr(data_to_send['markdown'][:100])}")
        print(f"🔍 DEBUG:   images: {nb_images} élément(s)")
        for i, img in enumerate(data_to_send["images"]):
            print(
                f"🔍 DEBUG:   image[{i}]: filename={img['filename']}, mimeType={img['mimeType']}, "
                f"data={len(img['data'])} car. base64"
            )

        try:
            result = eel.writeDocumentData(data_to_send)()
            print(f"🔍 DEBUG writeDocumentData retour → type={type(result).__name__}, valeur={repr(result)}")
            if result is None:
                print("✅ OUVERTURE TERMINÉE: document chargé (retour: None/undefined — normal si JS ne retourne rien)")
            elif result:
                print("✅ OUVERTURE TERMINÉE: document chargé dans l'éditeur")
            else:
                print(
                    f"⚠️ OUVERTURE: writeDocumentData a retourné {repr(result)} "
                    "(le document peut quand même être chargé)"
                )
            return True
        except Exception as e:
            print(f"❌ OUVERTURE: Erreur appel writeDocumentData: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            return False


class DiskDocumentStore(ports.DocumentStore):
    """Documents sur le disque, « façon Arduino » :

    directory/name/
    ├── name.md
    └── images/
        ├── photo_xxx.png
        └── schema_xxx.jpg
    """

    def save(self, document, directory, name):
        """Écrit le document (style Arduino : on écrase le contenu existant).
        Renvoie le dossier du document, None si le .md n'a pas pu être écrit"""
        print(f"💾 SAUVEGARDE: Début pour '{name}' dans '{directory}'")
        doc_dir = os.path.join(directory, name)
        images_dir = os.path.join(doc_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        print(f"📁 SAUVEGARDE: Dossier créé/existant: {doc_dir}")

        md_path = os.path.join(doc_dir, f"{name}.md")
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(document.markdown)
            print(f"✅ SAUVEGARDE: Fichier MD écrit: {md_path}")
        except Exception as e:
            print(f"❌ SAUVEGARDE: Erreur écriture MD: {e}")
            return None

        images_saved = 0
        for image in document.images:
            try:
                with open(os.path.join(images_dir, image.filename), "wb") as f:
                    f.write(image.content)
                images_saved += 1
                print(f"  🖼️ Image sauvée: {image.filename} ({len(image.content)} octets)")
            except Exception as e:
                print(f"  ❌ Erreur image '{image.filename}': {e}")

        print(f"✅ SAUVEGARDE TERMINÉE: {md_path} + {images_saved} image(s)")
        return doc_dir

    def load(self, path):
        """Lit le document désigné par son dossier OU par son fichier .md (principe Arduino :
        les deux fonctionnent pareil). Renvoie (document, dossier du document), None en cas d'erreur"""
        print(f"📂 OUVERTURE: Chemin reçu: '{path}'")

        if path.endswith(".md") and os.path.isfile(path):
            doc_dir = os.path.dirname(path)
            print(f"📂 OUVERTURE: Fichier .md détecté → dossier déduit: {doc_dir}")
        elif os.path.isdir(path):
            doc_dir = path
            print("📂 OUVERTURE: Dossier sélectionné directement")
        else:
            print(f"❌ OUVERTURE: Chemin invalide (ni dossier, ni fichier .md): {path}")
            return None

        # Convention : nom du dossier = nom du fichier .md
        document_name = os.path.basename(doc_dir)
        md_path = os.path.join(doc_dir, f"{document_name}.md")
        images_dir = os.path.join(doc_dir, "images")

        if not os.path.exists(md_path):
            print(f"❌ OUVERTURE: Fichier non trouvé: {md_path}")
            return None
        try:
            with open(md_path, encoding="utf-8") as f:
                markdown = f.read()
            print(f"📄 OUVERTURE: Markdown lu ({len(markdown)} caractères)")
        except Exception as e:
            print(f"❌ OUVERTURE: Erreur lecture MD: {e}")
            return None

        images = []
        if os.path.exists(images_dir):
            for filename in os.listdir(images_dir):
                image_path = os.path.join(images_dir, filename)
                if not os.path.isfile(image_path):
                    continue
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type or not mime_type.startswith("image/"):
                    print(f"  ⚠️ Fichier ignoré (pas une image): {filename}")
                    continue
                try:
                    with open(image_path, "rb") as f:
                        images.append(ports.Image(filename=filename, content=f.read(), mime_type=mime_type))
                    print(f"  🖼️ Image chargée: {filename} ({mime_type})")
                except Exception as e:
                    print(f"  ❌ Erreur lecture image '{filename}': {e}")
        else:
            print("📁 OUVERTURE: Pas de dossier images/ (document texte seul)")

        return ports.Document(markdown=markdown, images=images), doc_dir


class GeminiModel(ports.AIModel):
    """Modèle Gemini"""

    def __init__(self, client):
        self.client = client
        self.config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=GEMINI_THINKING_LEVEL,
                include_thoughts=True,
            ),
        )

    def stream(self, prompt):
        """Morceaux de réflexion et de réponse, puis un dernier morceau avec les jetons consommés.
        Les erreurs de Gemini deviennent des ports.AIModelError"""
        last_response = None
        try:
            for response in self.client.models.generate_content_stream(
                model=GEMINI_MODEL, contents=prompt, config=self.config
            ):
                last_response = response
                if not response.candidates:
                    continue
                if not response.candidates[0].content or not response.candidates[0].content.parts:
                    continue
                for part in response.candidates[0].content.parts:
                    if part.text:
                        yield ports.AIChunk(text=part.text, thought=bool(part.thought))
        except genai_errors.ServerError as e:
            raise ports.AIModelError(f"Erreur serveur Gemini: {e}") from e
        except genai_errors.APIError as e:
            raise ports.AIModelError(f"Erreur API Gemini: {e}") from e

        usage = getattr(last_response, "usage_metadata", None)
        if usage:
            yield ports.AIChunk(
                usage={
                    "input": getattr(usage, "prompt_token_count", "N/A"),
                    "output": getattr(usage, "candidates_token_count", "N/A"),
                    "thinking": getattr(usage, "thoughts_token_count", "N/A"),
                    "total": getattr(usage, "total_token_count", "N/A"),
                }
            )


# Instances partagées par les boutons du panneau (aucun effet de bord à la construction)
editeur_eel = EelEditor()
stockage_documents = DiskDocumentStore()


# --- Fonctions de tracking état éditeur (appelées par React) ---
# Variables globales pour accès depuis les callbacks Eel
root_global = None
status_label_global = None
streaming_text_global = None  # Zone de texte pour le streaming IA


def update_streaming_text(text, clear=False):
    """Met à jour la zone de texte du streaming IA (thread-safe)"""
    global root_global, streaming_text_global
    if root_global and streaming_text_global:

        def _update():
            streaming_text_global.configure(state="normal")
            if clear:
                streaming_text_global.delete("1.0", "end")
            streaming_text_global.insert("end", text)
            streaming_text_global.see("end")  # Auto-scroll
            streaming_text_global.configure(state="disabled")

        root_global.after(0, _update)


@eel.expose
def on_editor_open():
    """Appelé par React quand l'éditeur est monté"""
    global editeur_lance, lancement_editeur_en_cours, root_global, status_label_global, last_editor_activity
    editeur_lance = True
    lancement_editeur_en_cours = False  # Le lancement est terminé : l'éditeur est prêt
    last_editor_activity = time.time()  # Marquer l'activité
    print(f"✅ Éditeur ouvert (notifié par React) - Timestamp: {last_editor_activity}")
    # Mettre à jour la GUI si disponible
    if root_global and status_label_global:
        root_global.after(0, lambda: status_label_global.config(text="✅ Éditeur ouvert"))


@eel.expose
def on_editor_close():
    """Appelé par React avant la fermeture de la fenêtre"""
    global editeur_lance, root_global, status_label_global, last_editor_activity
    editeur_lance = False
    last_editor_activity = None  # Réinitialiser le timestamp
    print("🔴 Éditeur fermé (notifié par React)")
    # Mettre à jour la GUI si disponible
    if root_global and status_label_global:
        root_global.after(0, lambda: status_label_global.config(text="🔴 Éditeur fermé"))


def nettoyer_html_tags(text):
    """Supprime les balises HTML problématiques pour reportlab"""
    # Remplacer les marqueurs __BOLD_n__ par des séparateurs horizontaux MD
    text, bold_count = note.replace_bold_markers(text)
    if bold_count > 0:
        log_message(f"🔄 NETTOYAGE: {bold_count} marqueurs __BOLD_n__ remplacés par des séparateurs ---")

    # Supprimer les balises <span> avec styles
    text = re.sub(r"<span[^>]*>", "", text)
    text = re.sub(r"</span>", "", text)

    # Supprimer seulement les émojis problématiques pour reportlab
    text = re.sub(r"[🎉🎯🔧📊📝📄✅❌⚙️🚀🔍✏️🧠🔢💾🎮📋💡🤖📖🔗🪟📁⏳🔄💭]", "", text)

    # Nettoyer les caractères spéciaux
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Remettre les balises autorisées
    text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    text = text.replace("&lt;u&gt;", "<u>").replace("&lt;/u&gt;", "</u>")

    return text


def convertir_markdown_vers_paragraphes(contenu_md):
    """Convertit le contenu Markdown en paragraphes reportlab (VERSION CORRIGÉE PDF)"""

    # Styles reportlab
    styles = getSampleStyleSheet()

    # Styles personnalisés
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.darkblue,
        spaceAfter=15,
        alignment=1,  # Centré
    )

    heading1_style = ParagraphStyle(
        "CustomHeading1",
        parent=styles["Heading1"],
        fontSize=12,
        textColor=colors.darkblue,
        spaceBefore=12,
        spaceAfter=8,
    )

    heading2_style = ParagraphStyle(
        "CustomHeading2",
        parent=styles["Heading2"],
        fontSize=10,
        textColor=colors.darkslategray,
        spaceBefore=10,
        spaceAfter=6,
    )

    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=9,  # Plus gros pour meilleure lisibilité
        spaceBefore=6,
        spaceAfter=6,
        leftIndent=0,
        rightIndent=0,
    )

    code_style = ParagraphStyle(
        "CustomCode",
        parent=normal_style,
        fontSize=9,  # Plus gros pour meilleure lisibilité
        fontName="Helvetica",  # Police normale au lieu de Courier
        backgroundColor=colors.lightblue,  # Couleur plus visible
        borderWidth=2,
        borderColor=colors.darkblue,
        leftIndent=15,
        rightIndent=15,
        spaceBefore=8,
        spaceAfter=8,
        borderPadding=10,  # Plus d'espace autour du texte
    )

    # Parsing simple du Markdown
    paragraphes = []
    lignes = contenu_md.split("\n")
    in_code_block = False

    for ligne in lignes:
        ligne_original = ligne
        ligne = ligne.strip()

        if not ligne and not in_code_block:
            paragraphes.append(Spacer(1, 4))
            continue

        # Gestion des blocs de code (```)
        if ligne.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            # Dans un bloc de code, garder le formatage original
            text_clean = nettoyer_html_tags(ligne_original.rstrip())
            if text_clean.strip():  # Éviter les lignes complètement vides
                paragraphes.append(Paragraph(text_clean, code_style))
            continue

        # Nettoyer les balises HTML pour PDF
        ligne_clean = nettoyer_html_tags(ligne)

        # Titre principal (# )
        if ligne_clean.startswith("# "):
            text = ligne_clean[2:].strip()
            paragraphes.append(Paragraph(text, title_style))

        # Sous-titre niveau 1 (## )
        elif ligne_clean.startswith("## "):
            text = ligne_clean[3:].strip()
            paragraphes.append(Paragraph(text, heading1_style))

        # Sous-titre niveau 2 (### )
        elif ligne_clean.startswith("### "):
            text = ligne_clean[4:].strip()
            paragraphes.append(Paragraph(text, heading2_style))

        # Ligne de séparation (---)
        elif ligne_clean.startswith("---"):
            paragraphes.append(Spacer(1, 8))

        # Liste à puces (- ou *)
        elif ligne_clean.startswith("- ") or ligne_clean.startswith("* "):
            text = ligne_clean[2:].strip()
            paragraphes.append(Paragraph(f"• {text}", normal_style))

        # Texte normal
        else:
            # Gérer le gras inline (**texte**)
            ligne_final = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", ligne_clean)

            # Gérer l'italique inline (*texte*)
            ligne_final = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", ligne_final)

            if ligne_final.strip():  # Éviter les paragraphes vides
                paragraphes.append(Paragraph(ligne_final, normal_style))

    return paragraphes


def generer_pdf_reportlab(contenu_final, pdf_filepath):
    """Génère un PDF avec reportlab (VERSION CORRIGÉE POUR SPAN TAGS)"""
    try:
        log_message("📁 ÉTAPE: Génération PDF avec reportlab...")

        # Créer le document PDF
        doc = SimpleDocTemplate(
            pdf_filepath,
            pagesize=A4,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        # Convertir le Markdown en éléments reportlab
        elements = convertir_markdown_vers_paragraphes(contenu_final)

        # Construire le PDF
        doc.build(elements)

        log_message(f"✅ SUCCÈS: Fichier .pdf créé → {pdf_filepath}")
        return pdf_filepath

    except Exception as e:
        log_message(f"❌ ÉCHEC: Erreur génération PDF → {e}")
        log_message("💡 INFO: Tentative d'archivage PDF échouée")
        return None


def sauvegarder_rapport(
    contenu_original, logs_etapes, streaming_gemini, contenu_traite, debrief_correction, stats_tokens=None
):
    """Sauvegarde le rapport COMPLET en PDF uniquement"""
    if not contenu_traite or not contenu_traite.strip():
        log_message("⚠️ ATTENTION: Aucun contenu traité à sauvegarder")
        return None, None

    # Créer le dossier reports s'il n'existe pas
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Générer un nom de fichier avec timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = os.path.join(REPORTS_DIR, f"rapport_complet_{timestamp}")

    log_message(f"💾 SAUVEGARDE: Création du fichier PDF {base_filename}.pdf")

    # ÉTAPE 1: Préparer le contenu complet avec TOUS les logs
    log_message("🔧 ÉTAPE: Préparation du rapport complet...")
    contenu_final = report.build_report_markdown(
        original_note=contenu_original,
        step_logs=logs_etapes,
        ai_stream=streaming_gemini,
        processed_note=contenu_traite,
        correction_debrief=debrief_correction,
        token_stats=stats_tokens,
        model=GEMINI_MODEL,
        thinking_level=GEMINI_THINKING_LEVEL.value,
        generated_at=datetime.now(),
    )
    log_message("✅ SUCCÈS: Rapport complet préparé")

    # ÉTAPE 2: Pas de sauvegarde MD (PDF uniquement)
    md_filepath = None  # MD non sauvegardé (PDF uniquement)

    # ÉTAPE 3: Générer le PDF directement (archivage uniquement)
    log_message("📁 ÉTAPE: Génération PDF directement...")
    pdf_filepath = generer_pdf_reportlab(contenu_final, f"{base_filename}.pdf")

    # BILAN FINAL
    log_message("\n📊 BILAN SAUVEGARDE PDF:")
    log_message("=" * 30)

    if md_filepath:
        log_message(f"✅ Markdown : {os.path.basename(md_filepath)}")
    else:
        log_message("⚠️ Markdown : Non sauvegardé (PDF uniquement)")

    if pdf_filepath:
        log_message(f"✅ PDF      : {os.path.basename(pdf_filepath)}")
    else:
        log_message("❌ PDF      : ÉCHEC")

    log_message("=" * 30)

    return md_filepath, pdf_filepath


# --- Fonctions Gemini ---

GEMINI_API_KEY_PLACEHOLDER = "YOUR_GEMINI_API_KEY_HERE"


def lire_cle_api():
    """Lit la clé API dans GeminiKey.txt (ignore lignes vides et commentaires #)"""
    # utf-8-sig : tolère le BOM ajouté par le Bloc-notes Windows
    with open(os.path.join(APP_DIR, "GeminiKey.txt"), encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return ""


def init_gemini_client():
    """Initialise le client Gemini avec la clé API"""
    try:
        api_key = lire_cle_api()
        if not api_key:
            log_message("❌ ÉCHEC: Aucune clé API trouvée dans GeminiKey.txt")
            return None
        if api_key == GEMINI_API_KEY_PLACEHOLDER:
            log_message("❌ ÉCHEC: GeminiKey.txt contient encore la valeur du template, remplacez-la par votre clé")
            return None
        # Seuls les 4 derniers caractères : ce log est recopié dans les rapports PDF
        log_message(f"🔑 INFO: Clé API chargée (...{api_key[-4:]})")
        return genai.Client(api_key=api_key)
    except FileNotFoundError:
        log_message(f"❌ ÉCHEC: Fichier GeminiKey.txt introuvable dans {APP_DIR}")
        return None
    except Exception as e:
        log_message(f"❌ ÉCHEC: Erreur initialisation Gemini: {e}")
        return None


def lire_prompto_dys():
    """Lit promptodys.prompt : la copie embarquée dans l'exécutable PyInstaller,
    ou celle du dossier du script en mode développement"""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    try:
        with open(os.path.join(base_path, "promptodys.prompt"), encoding="utf-8") as f:
            contenu = f.read()

        if "[TEXTE]" not in contenu:
            log_message("❌ ÉCHEC: Balise [TEXTE] manquante dans promptodys.prompt")
            return None

        return contenu
    except FileNotFoundError:
        log_message("❌ ÉCHEC: Fichier promptodys.prompt introuvable")
        return None
    except Exception as e:
        log_message(f"❌ ÉCHEC: Erreur lecture promptodys.prompt: {e}")
        return None


def traitement_gemini(annulation):
    """Traitement IA Gemini : client → modèle de prompt → cas d'usage processing.process_note → rapport PDF

    annulation : threading.Event propre à ce traitement, déclenché par le bouton « Abandonner ».
    Un traitement abandonné s'arrête à la sortie du flux, sans rien écrire dans l'éditeur ni le PDF.

    Renvoie True si le traitement est allé jusqu'au bout, False en cas d'échec ou d'abandon.
    """
    # Nouveau traitement : logs du rapport et console vidés AVANT le premier log,
    # sinon l'effacement (traité dans l'ordre par root.after) ferait disparaître les étapes déjà affichées
    global logs_complets
    logs_complets = []
    update_streaming_text("", clear=True)

    log_message("\n🤖 DÉMARRAGE: TRAITEMENT IA GEMINI (ANNULABLE)")
    log_message("=" * 50)

    # 1. Initialiser le client et sa configuration
    log_message("🔑 ÉTAPE 1: Initialisation du client Gemini...")
    client = init_gemini_client()
    if not client:
        log_message("❌ ÉCHEC: Impossible d'initialiser Gemini")
        return False
    modele = GeminiModel(client)
    log_message(
        f"✅ SUCCÈS: Client Gemini initialisé (Modèle: {GEMINI_MODEL}, Thinking level: {GEMINI_THINKING_LEVEL.value})"
    )

    # 2. Lire le modèle de prompt
    log_message("\n📋 ÉTAPE 2: Lecture du template promptodys.prompt...")
    prompt_template = lire_prompto_dys()
    if not prompt_template:
        log_message("❌ ÉCHEC: Impossible de lire promptodys.prompt")
        return False
    log_message("✅ SUCCÈS: Template promptodys.prompt chargé")

    # Logs des étapes 1 et 2, complétés par ceux de la préparation (étapes 3 et 4) pour le rapport
    logs_avant_traitement = logs_complets.copy()

    # 3 à 8. Lecture de l'éditeur, prompt, flux IA, extraction, injection, jetons
    resultat = processing.process_note(editeur_eel, modele, prompt_template, annulation, datetime.now().date())
    if resultat.status is not processing.ProcessingStatus.COMPLETED:
        return False

    # 9. Sauvegarde automatique PDF uniquement
    log_message("\n💾 ÉTAPE 9: Sauvegarde automatique rapport PDF...")
    md_file, pdf_file = sauvegarder_rapport(
        contenu_original=resultat.original_note,
        logs_etapes=logs_avant_traitement + resultat.step_logs,
        streaming_gemini=resultat.ai_stream,
        contenu_traite=resultat.processed_note,
        debrief_correction=resultat.correction_debrief,
        stats_tokens=resultat.token_stats,
    )

    if pdf_file:
        log_message("🎉 SUCCÈS: Rapport PDF sauvegardé !")
        log_message(f"📁 Rapport PDF dans {REPORTS_DIR}")
    else:
        log_message("⚠️ ATTENTION: Sauvegarde PDF échouée")

    log_message("\n🎉 TERMINÉ: Traitement IA Gemini avec capture complète terminé !")
    return True


# --- GUI Tkinter avec thème Sun Valley ---
# --- Variable globale pour tracker si l'éditeur est lancé ---
editeur_lance = False
# Lancement demandé, en attente du signal de React (on_editor_open) : évite un second lancement
lancement_editeur_en_cours = False
# Fermeture de l'éditeur demandée, en attente de sa confirmation : ignore un second clic sur Quitter
fermeture_en_cours = False

# Délai maximum d'attente de la fermeture de l'éditeur avant de quitter quand même
CLOSE_EDITOR_TIMEOUT_S = 3


def quitter_application():
    """Ferme le panneau de contrôle et termine le processus"""
    log_message("👋 Fermeture de l'application...")
    root_global.destroy()
    os._exit(0)  # Force la fermeture complète


def fermer_editeur_puis_quitter():
    """
    Demande à l'éditeur React de fermer sa fenêtre (closeEditor), attend sa confirmation
    (on_editor_close ou retour de eel.start() remettent editeur_lance à False), puis quitte.
    Sous Windows, Chrome s'arrête avec sa dernière fenêtre. Au-delà du délai, on quitte quand même.
    """
    log_message("📝 Fermeture de l'éditeur...")
    try:
        eel.closeEditor()
    except Exception as e:
        # Bundle sans closeEditor, ou connexion déjà fermée
        log_message(f"⚠️ Impossible de demander la fermeture de l'éditeur : {e}")
        quitter_application()
        return

    # Au-delà, on quitte sans attendre la confirmation de l'éditeur
    close_deadline = time.time() + CLOSE_EDITOR_TIMEOUT_S

    def attendre_fermeture():
        if not editeur_lance:
            log_message("✅ Éditeur fermé")
            quitter_application()
        elif time.time() >= close_deadline:
            log_message("⚠️ L'éditeur n'a pas confirmé sa fermeture : fermeture de l'application quand même")
            quitter_application()
        else:
            root_global.after(100, attendre_fermeture)

    root_global.after(100, attendre_fermeture)


def on_closing():
    """
    Intercepte la fermeture de la fenêtre GUI (X ou bouton Quitter).
    Si l'éditeur est ouvert, demande confirmation puis le ferme avant de quitter.
    L'état de l'éditeur est géré exclusivement par les callbacks React (on_editor_open/on_editor_close)
    et par le retour de eel.start() — plus fiable que la détection psutil.
    """
    global fermeture_en_cours

    if fermeture_en_cours:
        return  # Fermeture de l'éditeur déjà demandée, en attente de sa confirmation

    if editeur_lance:
        result = messagebox.askyesno(
            "PromptoDYS - Éditeur ouvert",
            "L'éditeur est ouvert.\n\n"
            "Fermer l'application fermera aussi l'éditeur.\n"
            "Pensez à sauvegarder votre document.\n\n"
            "Voulez-vous continuer ?",
            icon="warning",
        )
        if not result:
            log_message("⚠️ Fermeture annulée")
            return
        fermeture_en_cours = True
        fermer_editeur_puis_quitter()
        return

    # Pas d'éditeur ouvert, fermeture immédiate
    quitter_application()


# --- État de l'éditeur géré exclusivement par les callbacks React ---
# on_editor_open()  → editeur_lance = True  (React notifie l'ouverture), fin du lancement
# on_editor_close() → editeur_lance = False (React notifie la fermeture)
# lancer_eel()      → editeur_lance = False (eel.start() retourne/lève si crash)
# lancement_editeur_en_cours : du clic sur « Ouvrir l'éditeur » au signal de React (ou à l'échec)


def gui_control_panel():
    """
    GUI de contrôle avec Tkinter + sv_ttk (thème Windows 11)
    Panneau compact avec 3 boutons principaux
    """
    global root_global, status_label_global
    log_message("🖥️ Démarrage du panneau de contrôle GUI...")

    # --- Fonctions des boutons ---
    def btn_ouvrir_editeur():
        """Lance l'éditeur Eel dans un thread séparé"""
        global editeur_lance, lancement_editeur_en_cours

        if editeur_lance:
            log_message("📝 L'éditeur est déjà ouvert")
            status_label.config(text="✅ L'éditeur est déjà ouvert")
            return

        if lancement_editeur_en_cours:
            log_message("📝 L'éditeur est déjà en cours d'ouverture")
            status_label.config(text="⏳ Ouverture de l'éditeur en cours, veuillez patienter")
            return

        # Levé dès le clic : un second clic pendant l'attente du port ou de Chrome ne relance rien
        lancement_editeur_en_cours = True
        log_message("📝 Action: Lancement de l'éditeur...")
        status_label.config(text="⏳ Ouverture de l'éditeur en cours, veuillez patienter")
        root.update()

        def echec_ouverture(statut, message):
            """Échec du lancement : statut et popup, affichés par le thread de l'interface"""

            def _afficher():
                status_label.config(text=statut)
                messagebox.showerror("PromptoDYS - Éditeur non ouvert", message)

            root.after(0, _afficher)

        def lancer_eel():
            global editeur_lance, lancement_editeur_en_cours
            # Vérifier le port avant d'ouvrir Chrome : s'il est pris, Chrome afficherait
            # la page de l'autre programme. On n'ouvre alors aucune fenêtre.
            if not attendre_port_libre(EEL_PORT):
                log_message(f"❌ Le port {EEL_PORT} est utilisé par un autre programme : éditeur non ouvert")
                lancement_editeur_en_cours = False
                echec_ouverture(
                    f"❌ Port {EEL_PORT} déjà utilisé par un autre programme",
                    f"Un autre programme utilise le port {EEL_PORT},\n"
                    "nécessaire à l'éditeur.\n\n"
                    "Fermez les autres programmes ouverts,\n"
                    "ou redémarrez l'ordinateur, puis réessayez.",
                )
                return
            try:
                eel.start(
                    "index.html",
                    mode="chrome",
                    size=(1200, 800),
                    port=EEL_PORT,
                    cmdline_args=[
                        f"--app=http://localhost:{EEL_PORT}/index.html",
                        f"--user-data-dir={CHROME_PROFILE_DIR}",
                        "--disable-features=VizDisplayCompositor",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-default-apps",
                        "--disable-extensions",
                        "--disable-plugins",
                        "--window-size=1200,800",
                        "--window-position=100,100",
                    ],
                    block=True,
                )
            except Exception as e:
                log_message(f"❌ Erreur lancement éditeur: {e}")
                # Fallback
                try:
                    eel.start(
                        "index.html",
                        mode="chrome-app",
                        size=(1200, 800),
                        port=EEL_PORT,
                        cmdline_args=[
                            f"--user-data-dir={CHROME_PROFILE_DIR}",
                            "--no-first-run",
                            "--no-default-browser-check",
                        ],
                        block=True,
                    )
                except Exception as e2:
                    log_message(f"❌ Erreur fallback lancement éditeur: {e2}")
                    editeur_lance = False
                    lancement_editeur_en_cours = False
                    echec_ouverture(
                        "❌ Échec de l'ouverture de l'éditeur (voir les logs)",
                        "L'éditeur n'a pas pu s'ouvrir.\n\n"
                        "Vérifiez que Google Chrome est installé,\n"
                        "puis réessayez.\n\n"
                        "Le détail de l'erreur est dans la console.",
                    )
                    return

            # Quand l'éditeur se ferme, on met à jour le statut
            root.after(0, lambda: status_label.config(text="🔴 Éditeur fermé"))
            editeur_lance = False
            lancement_editeur_en_cours = False  # Si React n'a jamais signalé l'ouverture

        # Lancer dans un thread pour ne pas bloquer la GUI
        thread = threading.Thread(target=lancer_eel, daemon=True)
        thread.start()
        # « ✅ Éditeur ouvert » est affiché par on_editor_open(), quand React signale que l'éditeur est prêt

    def btn_sauvegarder_document():
        """Sauvegarde le document — toujours en mode "Enregistrer sous" (dialogue à chaque fois).
        Si un document est déjà ouvert, le dialogue pré-remplit le nom et le dossier courant."""
        global editeur_lance, current_document_path

        if not editeur_lance:
            messagebox.showwarning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\nVeuillez d'abord ouvrir l'éditeur\navant de sauvegarder.",
                icon="warning",
            )
            status_label.config(text="⚠️ Éditeur non ouvert")
            return

        log_message(
            f"🔍 DEBUG btn_sauvegarder: editeur_lance={editeur_lance}, current_document_path={current_document_path}"
        )

        # Toujours afficher le dialogue — pré-rempli si document déjà ouvert/sauvegardé
        initial_dir = os.path.dirname(current_document_path) if current_document_path else PROMPTO_DOCS_DIR
        initial_name = os.path.basename(current_document_path) if current_document_path else "nouveau_document"

        # Le dialogue se rouvre tant que le nom saisi est vide après assainissement
        while True:
            selected = filedialog.asksaveasfilename(
                title="Enregistrer le document PromptoDYS...",
                initialdir=initial_dir,
                initialfile=initial_name,
                defaultextension="",
                filetypes=[("Tous les fichiers", "*.*")],
            )
            if not selected:
                log_message("💾 Sauvegarde annulée par l'utilisateur")
                return

            save_dir, doc_name = documents.prepare_save_path(selected)
            if doc_name:
                break

            log_message(f"⚠️ Nom de document invalide: '{os.path.basename(selected)}'")
            messagebox.showwarning(
                "PromptoDYS - Nom invalide",
                "Le nom du document est vide\n"
                "ou commence par un point.\n\n"
                "Veuillez saisir un nom\n"
                "(lettres ou chiffres).",
                icon="warning",
            )
            initial_dir = os.path.dirname(selected)
            initial_name = "nouveau_document"

        status_label.config(text="⏳ Sauvegarde en cours...")
        root.update()

        def run_save():
            global current_document_path
            log_message(f"🔍 DEBUG run_save: doc_name='{doc_name}', save_dir='{save_dir}'")
            result = documents.save_document(editeur_eel, stockage_documents, save_dir, doc_name)
            if result:
                current_document_path = result
                root.after(0, lambda: status_label.config(text=f"✅ '{doc_name}' sauvegardé !"))
                log_message(f"✅ Document sauvegardé dans: {result}")
            else:
                root.after(0, lambda: status_label.config(text="❌ Erreur de sauvegarde"))

        thread = threading.Thread(target=run_save, daemon=True)
        thread.start()

    def btn_ouvrir_document():
        """Ouvre un document complet (texte + images) via filedialog — accepte dossier ou fichier .md
        Si l'éditeur n'est pas lancé, il est ouvert automatiquement avant le chargement."""
        global editeur_lance, current_document_path

        # 1. Choisir le fichier AVANT de lancer l'éditeur (le filedialog est indépendant)
        selected_path = filedialog.askopenfilename(
            title="Ouvrir un document PromptoDYS",
            initialdir=PROMPTO_DOCS_DIR,
            filetypes=[
                ("Documents Markdown", "*.md"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not selected_path:
            log_message("📂 Ouverture annulée par l'utilisateur")
            return

        # 2. Si l'éditeur n'est pas ouvert, le lancer automatiquement
        need_wait = not editeur_lance
        if need_wait:
            log_message("📂 Éditeur non ouvert → lancement automatique avant ouverture du document...")
            status_label.config(text="⏳ Lancement de l'éditeur...")
            root.update()
            btn_ouvrir_editeur()

        status_label.config(text="⏳ Ouverture en cours...")
        root.update()

        # 3. Attendre que l'éditeur soit prêt, puis charger le document
        def run_load():
            if need_wait:
                # Attendre le signal de React (on_editor_open → last_editor_activity)
                timeout = 30
                waited = 0
                log_message("⏳ Attente du signal React on_editor_open()...")
                while last_editor_activity is None and waited < timeout:
                    time.sleep(0.5)
                    waited += 0.5

                if last_editor_activity is None:
                    log_message("❌ Timeout: React n'a pas signalé on_editor_open() dans les 30 secondes")
                    root.after(0, lambda: status_label.config(text="❌ Éditeur non prêt (timeout)"))
                    return

                # Petit délai pour laisser React finir l'initialisation complète des composants
                time.sleep(1.5)

            log_message("✅ Éditeur prêt, chargement du document...")

            result = documents.open_document(editeur_eel, stockage_documents, selected_path)
            if result:
                global current_document_path
                # Mémoriser le dossier du document ouvert (comme Arduino retient le sketch ouvert)
                current_document_path = result
                doc_name = os.path.basename(current_document_path)
                log_message(f"📌 Document courant: {current_document_path}")
                root.after(0, lambda: status_label.config(text=f"✅ '{doc_name}' ouvert !"))
            else:
                root.after(0, lambda: status_label.config(text="❌ Erreur d'ouverture"))

        thread = threading.Thread(target=run_load, daemon=True)
        thread.start()

    def btn_traitement_ia():
        """Lance le traitement IA Gemini ou demande l'abandon"""
        global editeur_lance, annulation_en_cours

        # SI DÉJÀ EN COURS -> ABANDON IMMÉDIAT
        # Le thread de traitement ne peut pas être interrompu s'il attend Gemini :
        # on déclenche son jeton et on libère l'interface sans l'attendre.
        # S'il se réveille plus tard, il voit son jeton déclenché et s'arrête sans rien écrire.
        if annulation_en_cours is not None:
            log_message("\n🚫 ABANDON: Traitement IA arrêté par l'utilisateur.")
            annulation_en_cours.set()
            annulation_en_cours = None
            btn_ia.configure(text="🤖 Traiter la prise de note", state="normal")
            status_label.config(text="🚫 Traitement annulé")
            return

        # VÉRIFICATION 1: Connexion internet - SUPPRIMÉE
        log_message("\n🔍 VÉRIFICATION PRÉ-TRAITEMENT IA...")

        # VÉRIFICATION 2: Éditeur ouvert
        if not editeur_lance:
            log_message("⚠️ L'éditeur n'est pas ouvert !")
            messagebox.showwarning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\nVeuillez d'abord ouvrir l'éditeur\navant de lancer le traitement IA.",
                icon="warning",
            )
            status_label.config(text="⚠️ Éditeur non ouvert")
            return

        log_message("🤖 Action: Lancement du traitement IA...")
        status_label.config(text="⏳ Traitement IA en cours...")

        # Nouveau jeton d'annulation, propre à ce traitement. Il est enregistré AVANT root.update()
        # et le thread, pour qu'un second clic soit traité comme une demande d'abandon
        annulation = threading.Event()
        annulation_en_cours = annulation

        # Mise à jour du bouton en mode "Abandon"
        btn_ia.configure(text="⛔ Abandonner le traitement")
        root.update()

        def terminer_traitement(success):
            """Fin du traitement, exécutée sur le thread principal (via root.after)"""
            global annulation_en_cours
            # Traitement abandonné (et peut-être remplacé par un autre) : l'interface est déjà à jour
            if annulation_en_cours is not annulation:
                return
            annulation_en_cours = None
            log_message("🔄 FIN: Réinitialisation du bouton de contrôle")
            btn_ia.configure(text="🤖 Traiter la prise de note", state="normal")
            if success:
                status_label.config(text="✅ Traitement IA terminé !")
            else:
                status_label.config(text="❌ Échec du traitement IA (voir les logs)")

        # Lancer le traitement dans un thread pour ne pas bloquer la GUI
        # Ce thread ne modifie aucune variable d'état : il confie la fin au thread principal
        def run_traitement():
            success = False
            try:
                success = traitement_gemini(annulation)
            except Exception as e:
                if not annulation.is_set():
                    log_message(f"❌ Erreur critique IA: {e}")
            finally:
                root.after(0, lambda: terminer_traitement(success))

        thread = threading.Thread(target=run_traitement, daemon=True)
        thread.start()

    def btn_ouvrir_rapports():
        """Ouvre le dossier des rapports PDF dans l'explorateur Windows"""
        log_message("📂 Action: Ouverture du dossier reports...")
        reports_path = REPORTS_DIR

        # Créer le dossier s'il n'existe pas
        os.makedirs(reports_path, exist_ok=True)

        # Ouvrir le dossier dans l'explorateur Windows
        try:
            subprocess.Popen(f'explorer "{reports_path}"')
            status_label.config(text="📂 Dossier reports ouvert")
        except Exception as e:
            status_label.config(text=f"❌ Erreur ouverture: {str(e)[:20]}")
            log_message(f"❌ Erreur ouverture dossier: {e}")

    def btn_quitter():
        """Ferme l'application complète"""
        # Réutiliser la fonction on_closing pour la cohérence
        on_closing()

    # --- Création de la fenêtre principale ---
    root = tk.Tk()
    root.withdraw()  # Cachée jusqu'au calcul de sa taille (fin de la construction)
    root_global = root  # Référence globale pour les callbacks Eel
    root.title("PromptoDYS - Panneau de Contrôle")
    root.configure(bg="#F3F3F3")  # Fond gris
    root.resizable(True, True)  # Fenêtre redimensionnable

    # Intercepter la fermeture de la fenêtre (X rouge)
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # --- Icône de la fenêtre ---
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "prompto.png")
        icon_image = tk.PhotoImage(file=icon_path)
        root.iconphoto(True, icon_image)
        log_message(f"✅ Icône chargée: {icon_path}")
    except Exception as e:
        log_message(f"⚠️ Icône non chargée: {e}")

    # Appliquer le thème Sun Valley (mode clair)
    sv_ttk.set_theme("light")  # Thème clair Windows 11

    # --- Créer un style pour le fond gris ---
    style = ttk.Style()
    style.configure("Gray.TFrame", background="#F3F3F3")

    # sv_ttk applique sa palette (tk_setPalette) au prochain tour de boucle, sur tous les widgets tk,
    # après set_theme() et après chaque style.configure(). Sans cet update, les couleurs choisies
    # plus bas (bordure sombre des boutons, fonds) seraient écrasées par le gris clair du thème.
    # Aucun style ne doit être configuré après cette ligne. La fenêtre est encore cachée.
    root.update()

    # --- Zone défilante (si la fenêtre est plus petite que son contenu) ---
    canvas = tk.Canvas(root, bg="#F3F3F3", highlightthickness=0, bd=0, yscrollincrement=20)  # Défilement : 20px
    canvas_scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=canvas_scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    # La barre n'est packée que si le contenu dépasse (voir maj_defilement)

    # --- Frame principal avec padding (placé dans le canvas) ---
    main_frame = ttk.Frame(canvas, padding=(20, 20, 20, 20), style="Gray.TFrame")  # Fond gris
    main_frame_id = canvas.create_window((0, 0), window=main_frame, anchor="nw")

    def contenu_depasse():
        """Vrai si le contenu est plus haut que la zone visible"""
        return main_frame.winfo_reqheight() > canvas.winfo_height()

    def maj_defilement(event=None):
        """Met à jour la zone défilable et affiche la barre seulement si nécessaire"""
        canvas.configure(scrollregion=canvas.bbox("all"))
        # La barre ne change que la largeur du canvas, pas sa hauteur : pas d'oscillation
        if contenu_depasse():
            if not canvas_scrollbar.winfo_manager():  # Pas encore packée
                canvas_scrollbar.pack(side="right", fill="y", before=canvas)
        elif canvas_scrollbar.winfo_manager():
            canvas_scrollbar.pack_forget()
            canvas.yview_moveto(0)  # Revenir en haut quand tout tient

    def on_canvas_configure(event):
        """Cale la largeur du contenu sur celle du canvas"""
        canvas.itemconfigure(main_frame_id, width=event.width)
        maj_defilement()

    main_frame.bind("<Configure>", maj_defilement)
    canvas.bind("<Configure>", on_canvas_configure)

    # --- Titre avec logo ---
    title_frame = ttk.Frame(main_frame)
    title_frame.pack(pady=(0, 5))  # Réduit de 10 à 5

    # Charger le logo prompto pour le titre (redimensionné)
    try:
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "prompto.png")
        logo_image_title = tk.PhotoImage(file=logo_path)
        # Redimensionner le logo (subsample = diviser par n)
        logo_image_title = logo_image_title.subsample(5, 5)  # Réduit encore plus (de 4 à 5)
        logo_label = ttk.Label(title_frame, image=logo_image_title)
        logo_label.image = logo_image_title  # Garder une référence
        logo_label.pack(side="left", padx=(0, 15))
        log_message("✅ Logo titre chargé")
    except Exception as e:
        log_message(f"⚠️ Logo titre non chargé: {e}")

    title_label = ttk.Label(
        title_frame,
        text="PromptoDYS",
        font=("Segoe UI", 24, "bold"),  # Réduit de 32 à 24
    )
    title_label.pack(side="left")

    # --- Fonctions pour effets de survol sur boutons tk.Button ---
    def on_button_enter(event, btn):
        """Effet au survol : bordure bleue, fond bleu clair, texte bleu"""
        btn.config(
            bg="#E3F2FD",  # Fond bleu clair
            fg="#0078D4",  # Texte bleu
            highlightbackground="#0078D4",  # Bordure bleue (épaisseur inchangée : la mise en page ne bouge pas)
        )

    def on_button_leave(event, btn):
        """Retour à l'état normal"""
        btn.config(
            bg="#FFFFFF",  # Fond blanc
            fg="#1F1F1F",  # Texte noir
            highlightbackground="#333333",  # Bordure sombre
        )

    def on_button_press(event, btn):
        """Effet au clic : enfoncement visuel"""
        btn.config(relief="sunken")

    def on_button_release(event, btn):
        """Retour au relief normal après clic"""
        btn.config(relief="raised")

    # --- Boutons (tk.Button classiques pour bordures épaisses) ---
    # Bouton 1: Ouvrir l'éditeur
    btn1 = tk.Button(
        main_frame,
        text="📝 Ouvrir l'Éditeur",
        command=btn_ouvrir_editeur,
        font=("Segoe UI", 16, "bold"),
        bg="#FFFFFF",  # Fond blanc
        fg="#1F1F1F",  # Texte noir
        relief="raised",
        bd=12,  # Bordure très épaisse
        highlightbackground="#333333",  # Bordure sombre
        highlightthickness=12,  # Épaisseur bordure highlight
        padx=20,
        pady=15,
        cursor="hand2",
    )
    btn1.pack(pady=8, fill="x", padx=20)
    # Lier les événements de survol
    btn1.bind("<Enter>", lambda e: on_button_enter(e, btn1))
    btn1.bind("<Leave>", lambda e: on_button_leave(e, btn1))
    btn1.bind("<ButtonPress-1>", lambda e: on_button_press(e, btn1))
    btn1.bind("<ButtonRelease-1>", lambda e: on_button_release(e, btn1))

    # --- Section Document : Sauvegarder / Ouvrir (côte à côte dans un LabelFrame) ---
    doc_frame = ttk.LabelFrame(main_frame, text="📄 Document", padding=(10, 5))
    doc_frame.pack(fill="x", padx=20, pady=8)

    # Configurer 2 colonnes de poids égal pour répartir l'espace
    doc_frame.columnconfigure(0, weight=1)
    doc_frame.columnconfigure(1, weight=1)

    # Bouton Sauvegarder (colonne gauche)
    btn_save = tk.Button(
        doc_frame,
        text="💾 Sauvegarder",
        command=btn_sauvegarder_document,
        font=("Segoe UI", 13, "bold"),
        bg="#FFFFFF",
        fg="#1F1F1F",
        relief="raised",
        bd=8,
        highlightbackground="#333333",
        highlightthickness=8,
        padx=10,
        pady=10,
        cursor="hand2",
    )
    btn_save.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=5)
    btn_save.bind("<Enter>", lambda e: on_button_enter(e, btn_save))
    btn_save.bind("<Leave>", lambda e: on_button_leave(e, btn_save))
    btn_save.bind("<ButtonPress-1>", lambda e: on_button_press(e, btn_save))
    btn_save.bind("<ButtonRelease-1>", lambda e: on_button_release(e, btn_save))

    # Bouton Ouvrir (colonne droite)
    btn_open = tk.Button(
        doc_frame,
        text="📂 Ouvrir",
        command=btn_ouvrir_document,
        font=("Segoe UI", 13, "bold"),
        bg="#FFFFFF",
        fg="#1F1F1F",
        relief="raised",
        bd=8,
        highlightbackground="#333333",
        highlightthickness=8,
        padx=10,
        pady=10,
        cursor="hand2",
    )
    btn_open.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=5)
    btn_open.bind("<Enter>", lambda e: on_button_enter(e, btn_open))
    btn_open.bind("<Leave>", lambda e: on_button_leave(e, btn_open))
    btn_open.bind("<ButtonPress-1>", lambda e: on_button_press(e, btn_open))
    btn_open.bind("<ButtonRelease-1>", lambda e: on_button_release(e, btn_open))

    # Bouton 2: Traitement IA
    btn_ia = tk.Button(
        main_frame,
        text="🤖 Traiter la prise de note",
        command=btn_traitement_ia,
        font=("Segoe UI", 16, "bold"),
        bg="#FFFFFF",
        fg="#1F1F1F",
        relief="raised",
        bd=12,
        highlightbackground="#333333",
        highlightthickness=12,
        padx=20,
        pady=15,
        cursor="hand2",
    )
    btn_ia.pack(pady=8, fill="x", padx=20)
    btn_ia.bind("<Enter>", lambda e: on_button_enter(e, btn_ia))
    btn_ia.bind("<Leave>", lambda e: on_button_leave(e, btn_ia))
    btn_ia.bind("<ButtonPress-1>", lambda e: on_button_press(e, btn_ia))
    btn_ia.bind("<ButtonRelease-1>", lambda e: on_button_release(e, btn_ia))

    # Bouton 3: Ouvrir rapports PDF
    btn3 = tk.Button(
        main_frame,
        text="📂 Voir les rapports PDF",
        command=btn_ouvrir_rapports,
        font=("Segoe UI", 16, "bold"),
        bg="#FFFFFF",
        fg="#1F1F1F",
        relief="raised",
        bd=12,
        highlightbackground="#333333",
        highlightthickness=12,
        padx=20,
        pady=15,
        cursor="hand2",
    )
    btn3.pack(pady=8, fill="x", padx=20)
    btn3.bind("<Enter>", lambda e: on_button_enter(e, btn3))
    btn3.bind("<Leave>", lambda e: on_button_leave(e, btn3))
    btn3.bind("<ButtonPress-1>", lambda e: on_button_press(e, btn3))
    btn3.bind("<ButtonRelease-1>", lambda e: on_button_release(e, btn3))

    # --- Séparateur ---
    separator = ttk.Separator(main_frame, orient="horizontal")
    separator.pack(fill="x", pady=10)  # Réduit de 20 à 10

    # --- Barre de statut ---
    status_label = ttk.Label(
        main_frame,
        text="🟢 Prêt",
        font=("Segoe UI", 14),  # Réduit de 18 à 14
    )
    status_label.pack(pady=5)  # Réduit de 10 à 5
    status_label_global = status_label  # Référence globale pour les callbacks Eel

    # --- Zone de texte pour le streaming IA ---
    # Renommé pour refléter qu'il contient tous les logs
    streaming_frame = ttk.LabelFrame(main_frame, text="📝 Console / Logs", padding=10)
    streaming_frame.pack(fill="both", expand=False, pady=10)

    # Créer une zone de texte avec scrollbar
    streaming_text = tk.Text(
        streaming_frame,
        height=4,  # Exactement 4 lignes complètes
        width=60,
        font=("Consolas", 10),  # Police légèrement plus petite pour logs
        wrap="word",
        state="disabled",  # Lecture seule
        bg="#f8f8f8",
        fg="#333333",
    )
    scrollbar = ttk.Scrollbar(streaming_frame, orient="vertical", command=streaming_text.yview)
    streaming_text.configure(yscrollcommand=scrollbar.set)

    streaming_text.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Référence globale pour le streaming
    global streaming_text_global
    streaming_text_global = streaming_text

    # --- Redirection de stdout ET stderr vers la GUI ---
    def update_gui_logs(msg):
        # Filtrer les messages vides
        if msg and msg.strip():
            update_streaming_text(msg)
        elif msg == "\n":
            update_streaming_text("\n")

    # Rediriger stdout (prints normaux)
    sys.stdout = RedirectText(update_gui_logs, is_stderr=False)
    # Rediriger stderr (erreurs, exceptions)
    sys.stderr = RedirectText(update_gui_logs, is_stderr=True)

    print("✅ Console et Erreurs redirigées vers la GUI")

    # --- Bouton Quitter (plus petit, en bas) ---
    btn_quit = tk.Button(
        main_frame,
        text="❌ Quitter",
        command=btn_quitter,
        font=("Segoe UI", 14),
        bg="#F5F5F5",
        fg="#666666",
        relief="raised",
        bd=8,
        highlightbackground="#999999",
        highlightthickness=8,
        padx=15,
        pady=10,
        cursor="hand2",
    )
    btn_quit.pack(pady=0)  # Aucune marge
    # Effets de survol spécifiques pour le bouton Quitter
    btn_quit.bind("<Enter>", lambda e: btn_quit.config(bg="#FFE6E6", fg="#CC0000", highlightbackground="#CC0000"))
    btn_quit.bind("<Leave>", lambda e: btn_quit.config(bg="#F5F5F5", fg="#666666", highlightbackground="#999999"))

    # --- Molette : défilement de la fenêtre ---
    def on_molette(event):
        """Fait défiler la fenêtre, sauf au-dessus de la console (qui a son propre défilement)"""
        try:
            widget = root.winfo_containing(event.x_root, event.y_root)
        except KeyError:
            return  # Widget interne à Tk, inconnu de tkinter (ex. : dialogue)
        if widget is None or widget is streaming_text or widget.winfo_toplevel() is not root:
            return
        if not contenu_depasse():
            return  # Tout tient : rien à faire défiler
        if sys.platform == "darwin":
            unites = -event.delta  # macOS : delta petit (±1, ±2...)
        else:
            unites = -3 * int(event.delta / 120)  # Windows : ±120 par cran, 3 unités par cran
            if unites == 0:
                unites = -1 if event.delta > 0 else 1  # Pavé tactile : delta inférieur à 120
        canvas.yview_scroll(unites, "units")

    root.bind_all("<MouseWheel>", on_molette)

    # --- Taille de la fenêtre calculée depuis le contenu ---
    root.update_idletasks()  # Calculer la taille demandée par chaque widget
    hauteur_ideale = main_frame.winfo_reqheight()  # Tout le contenu, padding et bouton Quitter compris
    hauteur_disponible = int(root.winfo_screenheight() * 0.9)  # 90 % de l'écran
    hauteur = min(hauteur_ideale, hauteur_disponible)
    largeur_ideale = main_frame.winfo_reqwidth()  # Largeur sous laquelle le contenu serait écrasé
    if hauteur_ideale > hauteur_disponible:
        largeur_ideale += canvas_scrollbar.winfo_reqwidth()  # La barre de défilement prend sa place à droite
    root.geometry(f"{largeur_ideale}x{hauteur}")
    root.minsize(largeur_ideale, hauteur)  # Taille minimale : rien de caché ni d'écrasé
    root.deiconify()  # Afficher la fenêtre à sa taille définitive

    # --- Lancer la boucle principale ---
    print("✅ Panneau de contrôle GUI prêt !")
    root.mainloop()


def main():
    """Lance l'application - GUI d'abord, éditeur via bouton"""
    # Avant la création de la fenêtre Tk, sinon l'interface est floue sous Windows
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)  # DPI per monitor
    except ImportError, AttributeError, OSError:
        pass  # Ignorer si non Windows

    configure_logger()
    log_message("🚀 Lancement de PromptoDYS...")
    log_message("💾 Sauvegarde automatique : PDF uniquement avec CAPTURE COMPLÈTE des logs")

    # Trouver le dossier web
    web_folder = find_web_folder()
    if not web_folder:
        log_message("💡 Placez votre build React dans le dossier 'build/'")
        return

    # Créer le dossier reports
    os.makedirs(REPORTS_DIR, exist_ok=True)
    log_message(f"📁 Dossier des rapports PDF : {REPORTS_DIR}")

    # Créer le dossier des documents et le profil Chrome de l'éditeur
    os.makedirs(PROMPTO_DOCS_DIR, exist_ok=True)
    log_message(f"📁 Dossier projets PromptoDYS : {PROMPTO_DOCS_DIR}")
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    log_message(f"🌐 Profil Chrome PromptoDYS : {CHROME_PROFILE_DIR}")

    # Initialiser Eel (préparation, mais ne lance pas encore)
    eel.init(web_folder)
    log_message("✅ Eel initialisé, prêt à lancer l'éditeur")

    # Lancer la GUI de contrôle (BLOQUANT - boucle principale)
    log_message("🖥️ Lancement du panneau de contrôle...")
    gui_control_panel()

    log_message("🔚 Application fermée")


if __name__ == "__main__":
    main()
