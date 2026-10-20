#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
- prompto.dys (template de traitement IA)
- build/index.html (interface web)

Fonctionnalités:
- Sauvegarde automatique des rapports en PDF uniquement
- Rendu Markdown professionnel dans les PDF avec reportlab
- Interface console simple et efficace
- Dossier reports/ créé automatiquement
- CAPTURE COMPLÈTE de tous les logs dans les rapports
"""

import eel
import os
import sys
import threading
import time
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

# Modèle Gemini utilisé (ex. "gemini-3.8-flash", "gemini-3.5-flash-lite")
GEMINI_MODEL = "gemini-3.8-flash"

# Niveau de réflexion Gemini 3.x
GEMINI_THINKING_LEVEL = types.ThinkingLevel.LOW

# --- Imports GUI Tkinter + sv_ttk ---
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sv_ttk  # Thème Sun Valley (Windows 11 look)
import subprocess  # Pour ouvrir le dossier reports

# --- VERSION ---
__version__ = "1.2.0"

try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)  # DPI per monitor
except:
    pass  # Ignorer si non Windows


# --- NOUVELLE VARIABLE POUR CAPTURER TOUS LES LOGS ---
logs_complets = []
historique_llm = []

# --- VARIABLES D'ÉTAT POUR L'ABANDON IA ---
abandon_ia = False
traitement_en_cours = False
btn_ia_global = None  # Référence au bouton pour changer son état

# --- VARIABLE POUR TRACKING TEMPOREL DE L'ÉDITEUR ---
last_editor_activity = None  # Timestamp de la dernière activité éditeur détectée

# --- CHEMIN DU DOCUMENT COURANT (style Arduino : mémorise le dernier save/open) ---
current_document_path = None  # Ex: "C:/.../PromptoDYS/MonDoc" → sauvegarde directe au prochain Ctrl+S




# Classe pour rediriger stdout vers la GUI
# Classe pour rediriger stdout/stderr vers la GUI tout en gardant la console
class RedirectText(object):
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
            try:
                self.terminal.write(message)
                self.terminal.flush()
            except:
                pass
        
        # Mettre à jour la GUI
        try:
            self.updater(message)
        except:
            pass # Éviter de planter si la GUI est fermée

    def flush(self):
        if self.terminal:
            try:
                self.terminal.flush()
            except:
                pass





def log_message(message):
    """Log un message dans la console ET le capture pour les rapports"""
    print(message, flush=True)
    # Les prints sont maintenant redirigés vers la GUI via stdout mais on garde l'ajout explicite aux logs complets
    # Capturer aussi dans les logs complets
    logs_complets.append(message)


def find_web_folder():
    """Trouve le dossier contenant index.html (compatible PyInstaller)"""
    import sys

    # Si on est dans un exécutable PyInstaller
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
        possible_folders = ['build_web', 'build']
    else:
        # Mode développement normal
        base_path = '.'
        possible_folders = ['build_web', 'build', 'dist', 'public', '.']

    for folder in possible_folders:
        index_path = os.path.join(base_path, folder, 'index.html')
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
        print(f'✅ SUCCÈS: Contenu récupéré ({len(content)} caractères)')
        return content
    except Exception as e:
        print(f'❌ ÉCHEC: Erreur lecture: {e}')
        return ''


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
        print(f'✅ SUCCÈS: Contenu injecté ({len(markdown_content)} caractères)')
        return True
    except Exception as e:
        print(f'❌ ÉCHEC: Erreur écriture: {e}')
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
os.makedirs(PROMPTO_DOCS_DIR, exist_ok=True)
print(f"📁 Dossier projets PromptoDYS: {PROMPTO_DOCS_DIR}")


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
    profile_dir = os.path.join(base_dir, "PromptoDYS", "ChromeProfile")
    os.makedirs(profile_dir, exist_ok=True)
    return profile_dir

CHROME_PROFILE_DIR = _get_chrome_profile_dir()
print(f"🌐 Profil Chrome PromptoDYS: {CHROME_PROFILE_DIR}")

# --- Fonctions de sauvegarde/ouverture de documents complets (texte + images) ---
# Principe "Arduino" : le dossier porte le même nom que le fichier .md principal

def save_document(document_name, save_directory):
    """
    💾 SAUVEGARDE COMPLÈTE: Récupère le document (texte + images) depuis l'éditeur
    et l'écrit sur le disque dans un dossier autonome.
    
    Structure créée :
        save_directory/document_name/
        ├── document_name.md
        └── images/
            ├── photo_xxx.png
            └── schema_xxx.jpg
    
    Args:
        document_name: Nom du document (ex: "MonDocument")
        save_directory: Chemin du dossier parent (ex: "C:/Users/Jean/Documents")
    
    Returns:
        str|False: Chemin du dossier créé si succès, False sinon
    """
    print(f"💾 SAUVEGARDE: Début pour '{document_name}' dans '{save_directory}'")
    
    # 1. Récupérer les données depuis l'éditeur JS (texte + images base64)
    print(f"🔍 DEBUG: editeur_lance={editeur_lance}, last_editor_activity={last_editor_activity}")
    print(f"🔍 DEBUG: Appel eel.readDocumentData()()...")
    try:
        data = eel.readDocumentData()()
        print(f"🔍 DEBUG readDocumentData retour → type={type(data).__name__}")
        if data is None:
            print(f"🔍 DEBUG readDocumentData → None (la fonction JS retourne undefined ou null)")
        elif isinstance(data, dict):
            print(f"🔍 DEBUG readDocumentData → dict avec clés: {list(data.keys())}")
            if 'markdown' in data:
                print(f"🔍 DEBUG   markdown: {len(data['markdown'])} caractères")
            if 'images' in data:
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
        return False
    
    if not data:
        print(f"❌ SAUVEGARDE: Aucune donnée reçue de l'éditeur (data est falsy: {repr(data)})")
        return False
    
    print(f"📄 SAUVEGARDE: Markdown reçu ({len(data.get('markdown', ''))} caractères)")
    print(f"🖼️ SAUVEGARDE: {len(data.get('images', []))} image(s) reçue(s)")
    
    # 2. Créer la structure de dossiers
    doc_dir = os.path.join(save_directory, document_name)
    images_dir = os.path.join(doc_dir, "images")
    
    # Gestion des conflits de noms (style Arduino : on écrase le contenu existant)
    os.makedirs(images_dir, exist_ok=True)
    print(f"📁 SAUVEGARDE: Dossier créé/existant: {doc_dir}")
    
    # 3. Écrire le fichier Markdown
    md_path = os.path.join(doc_dir, f"{document_name}.md")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(data["markdown"])
        print(f"✅ SAUVEGARDE: Fichier MD écrit: {md_path}")
    except Exception as e:
        print(f"❌ SAUVEGARDE: Erreur écriture MD: {e}")
        return False
    
    # 4. Écrire chaque image (décodage base64 → binaire)
    images_saved = 0
    for image in data.get("images", []):
        image_path = os.path.join(images_dir, image["filename"])
        try:
            image_bytes = base64.b64decode(image["data"])
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            images_saved += 1
            print(f"  🖼️ Image sauvée: {image['filename']} ({len(image_bytes)} octets)")
        except Exception as e:
            print(f"  ❌ Erreur image '{image['filename']}': {e}")
    
    print(f"✅ SAUVEGARDE TERMINÉE: {md_path} + {images_saved} image(s)")
    return doc_dir


def load_document(path):
    """
    📂 OUVERTURE COMPLÈTE: Lit un document depuis le disque et l'injecte dans l'éditeur.
    
    Accepte un chemin vers le dossier OU vers le fichier .md (principe Arduino :
    que l'utilisateur sélectionne le .md ou le dossier, ça fonctionne pareil).
    
    Args:
        path: Chemin vers le dossier du document OU vers le fichier .md
    
    Returns:
        bool: True si succès, False sinon
    """
    print(f"📂 OUVERTURE: Chemin reçu: '{path}'")
    
    # Détection intelligente : fichier .md ou dossier ?
    if path.endswith(".md") and os.path.isfile(path):
        # L'utilisateur a sélectionné le fichier .md directement
        doc_dir = os.path.dirname(path)
        print(f"📂 OUVERTURE: Fichier .md détecté → dossier déduit: {doc_dir}")
    elif os.path.isdir(path):
        # L'utilisateur a sélectionné le dossier
        doc_dir = path
        print(f"📂 OUVERTURE: Dossier sélectionné directement")
    else:
        print(f"❌ OUVERTURE: Chemin invalide (ni dossier, ni fichier .md): {path}")
        return False
    
    # Déduire les chemins (convention : nom du dossier = nom du fichier .md)
    document_name = os.path.basename(doc_dir)
    md_path = os.path.join(doc_dir, f"{document_name}.md")
    images_dir = os.path.join(doc_dir, "images")
    
    # 1. Lire le fichier Markdown
    if not os.path.exists(md_path):
        print(f"❌ OUVERTURE: Fichier non trouvé: {md_path}")
        return False
    
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        print(f"📄 OUVERTURE: Markdown lu ({len(markdown_content)} caractères)")
    except Exception as e:
        print(f"❌ OUVERTURE: Erreur lecture MD: {e}")
        return False
    
    # 2. Lire et encoder les images en base64
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
                    image_data = base64.b64encode(f.read()).decode("utf-8")
                
                images.append({
                    "filename": filename,
                    "data": image_data,
                    "mimeType": mime_type
                })
                print(f"  🖼️ Image chargée: {filename} ({mime_type})")
            except Exception as e:
                print(f"  ❌ Erreur lecture image '{filename}': {e}")
    else:
        print(f"📁 OUVERTURE: Pas de dossier images/ (document texte seul)")
    
    print(f"📤 OUVERTURE: Envoi à l'éditeur ({len(markdown_content)} car. + {len(images)} image(s))...")
    
    # 3. Envoyer à l'éditeur JS via le pont Eel
    print(f"🔍 DEBUG: editeur_lance={editeur_lance}, last_editor_activity={last_editor_activity}")
    print(f"🔍 DEBUG: Appel eel.writeDocumentData() avec {len(markdown_content)} car. + {len(images)} image(s)...")
    
    # Détail des données envoyées
    data_to_send = {
        "markdown": markdown_content,
        "images": images
    }
    print(f"🔍 DEBUG: data_to_send → clés={list(data_to_send.keys())}")
    print(f"🔍 DEBUG:   markdown: {len(data_to_send['markdown'])} car., début: {repr(data_to_send['markdown'][:100])}")
    print(f"🔍 DEBUG:   images: {len(data_to_send['images'])} élément(s)")
    for i, img in enumerate(data_to_send['images']):
        print(f"🔍 DEBUG:   image[{i}]: filename={img['filename']}, mimeType={img['mimeType']}, data={len(img['data'])} car. base64")
    
    try:
        result = eel.writeDocumentData(data_to_send)()
        
        print(f"🔍 DEBUG writeDocumentData retour → type={type(result).__name__}, valeur={repr(result)}")
        
        if result is None:
            print(f"✅ OUVERTURE TERMINÉE: '{document_name}' chargé (retour: None/undefined — normal si JS ne retourne rien)")
        elif result:
            print(f"✅ OUVERTURE TERMINÉE: '{document_name}' chargé dans l'éditeur")
        else:
            print(f"⚠️ OUVERTURE: writeDocumentData a retourné {repr(result)} (le document peut quand même être chargé)")
        return True
    except Exception as e:
        print(f"❌ OUVERTURE: Erreur appel writeDocumentData: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


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
    global editeur_lance, root_global, status_label_global, last_editor_activity
    editeur_lance = True
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


def preparer_contenu_rapport_complet(contenu_original, logs_etapes, streaming_gemini, contenu_traite,
                                     debrief_correction, stats_tokens=None):
    """Prépare le contenu COMPLET du rapport avec TOUS les logs - VERSION LISIBLE"""

    contenu_final = f"# Rapport PromptoDYS - Session Complète\n\n"
    contenu_final += f"**Date de génération :** {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n\n"

    # SECTION 1: Métadonnées
    contenu_final += "## 📊 Métadonnées de la Session\n\n"
    if stats_tokens:
        contenu_final += f"- **Input tokens :** {stats_tokens.get('input', 'N/A')}\n"
        contenu_final += f"- **Output tokens :** {stats_tokens.get('output', 'N/A')}\n"
        contenu_final += f"- **Thinking tokens :** {stats_tokens.get('thinking', 'N/A')}\n"
        contenu_final += f"- **Total tokens :** {stats_tokens.get('total', 'N/A')}\n\n"

    contenu_final += "---\n\n"

    # SECTION 2: Contenu Original
    contenu_final += "## 📄 Contenu Original de l'Éditeur\n\n"
    contenu_final += "**CONTENU ORIGINAL :**\n\n"
    for ligne in (contenu_original if contenu_original else "(Aucun contenu)").split('\n'):
        contenu_final += f"    {ligne}\n"
    contenu_final += "\n---\n\n"

    # SECTION 3: Log des Étapes de Traitement
    contenu_final += "## 🔧 Log Complet du Traitement IA\n\n"
    contenu_final += "**ÉTAPES DE TRAITEMENT :**\n\n"
    for log in logs_etapes:
        contenu_final += f"    {log}\n"
    contenu_final += "\n---\n\n"

    # SECTION 4: Streaming Gemini Complet
    contenu_final += "## 🤖 Streaming Gemini Complet\n\n"
    contenu_final += "**THINKING + RÉPONSE EN TEMPS RÉEL :**\n\n"
    for ligne in (streaming_gemini if streaming_gemini else "(Aucun streaming capturé)").split('\n'):
        contenu_final += f"    {ligne}\n"
    contenu_final += "\n---\n\n"

    # SECTION 5: Contenu Traité Final
    contenu_final += "## ✅ Contenu Traité Final (Résultat)\n\n"
    contenu_final += contenu_traite if contenu_traite else "(Aucun contenu traité)"
    contenu_final += "\n\n"
    contenu_final += "---\n\n"

    # SECTION 6: Débrief de Correction
    contenu_final += "## 📝 Débrief de la Correction par l'IA\n\n"
    contenu_final += debrief_correction if debrief_correction else "(Aucun débrief disponible)"
    contenu_final += "\n\n"
    contenu_final += "---\n\n"

    # SECTION 7: Footer
    contenu_final += "## 📋 Informations de Session\n\n"
    contenu_final += f"- **Script :** PromptoDYS avec capture complète des logs\n"
    contenu_final += f"- **Modèle IA :** {GEMINI_MODEL}\n"
    contenu_final += f"- **Thinking Level :** {GEMINI_THINKING_LEVEL.value.capitalize()}\n"
    contenu_final += f"- **Sauvegarde :** Automatique PDF uniquement\n\n"

    return contenu_final


def convertir_markdown_vers_paragraphes(contenu_md):
    """Convertit le contenu Markdown en paragraphes reportlab (VERSION CORRIGÉE PDF)"""

    # Styles reportlab
    styles = getSampleStyleSheet()

    # Styles personnalisés
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.darkblue,
        spaceAfter=15,
        alignment=1  # Centré
    )

    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=12,
        textColor=colors.darkblue,
        spaceBefore=12,
        spaceAfter=8
    )

    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=10,
        textColor=colors.darkslategray,
        spaceBefore=10,
        spaceAfter=6
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,  # Plus gros pour meilleure lisibilité
        spaceBefore=6,
        spaceAfter=6,
        leftIndent=0,
        rightIndent=0
    )

    code_style = ParagraphStyle(
        'CustomCode',
        parent=normal_style,
        fontSize=9,  # Plus gros pour meilleure lisibilité
        fontName='Helvetica',  # Police normale au lieu de Courier
        backgroundColor=colors.lightblue,  # Couleur plus visible
        borderWidth=2,
        borderColor=colors.darkblue,
        leftIndent=15,
        rightIndent=15,
        spaceBefore=8,
        spaceAfter=8,
        borderPadding=10  # Plus d'espace autour du texte
    )

    # Fonction pour nettoyer les balises span et autres problèmes HTML
    def nettoyer_html_tags(text):
        """Supprime les balises HTML problématiques pour reportlab"""
        # Remplacer les marqueurs __BOLD_n__ par des séparateurs horizontaux MD
        bold_count = len(re.findall(r'__BOLD_\d+__', text))
        if bold_count > 0:
            log_message(f"🔄 NETTOYAGE: {bold_count} marqueurs __BOLD_n__ remplacés par des séparateurs ---")
        text = re.sub(r'__BOLD_\d+__', '---', text)
        
        # Supprimer les balises <span> avec styles
        text = re.sub(r'<span[^>]*>', '', text)
        text = re.sub(r'</span>', '', text)

        # Supprimer seulement les émojis problématiques pour reportlab
        text = re.sub(r'[🎉🎯🔧📊📝📄✅❌⚙️🚀🔍✏️🧠🔢💾🎮📋💡🤖📖🔗🪟📁⏳🔄💭]', '', text)

        # Nettoyer les caractères spéciaux
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Remettre les balises autorisées
        text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
        text = text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
        text = text.replace('&lt;u&gt;', '<u>').replace('&lt;/u&gt;', '</u>')

        return text

    # Parsing simple du Markdown
    paragraphes = []
    lignes = contenu_md.split('\n')
    in_code_block = False

    for ligne in lignes:
        ligne_original = ligne
        ligne = ligne.strip()

        if not ligne and not in_code_block:
            paragraphes.append(Spacer(1, 4))
            continue

        # Gestion des blocs de code (```)
        if ligne.startswith('```'):
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
        if ligne_clean.startswith('# '):
            text = ligne_clean[2:].strip()
            paragraphes.append(Paragraph(text, title_style))

        # Sous-titre niveau 1 (## )
        elif ligne_clean.startswith('## '):
            text = ligne_clean[3:].strip()
            paragraphes.append(Paragraph(text, heading1_style))

        # Sous-titre niveau 2 (### )
        elif ligne_clean.startswith('### '):
            text = ligne_clean[4:].strip()
            paragraphes.append(Paragraph(text, heading2_style))

        # Ligne de séparation (---)
        elif ligne_clean.startswith('---'):
            paragraphes.append(Spacer(1, 8))

        # Liste à puces (- ou *)
        elif ligne_clean.startswith('- ') or ligne_clean.startswith('* '):
            text = ligne_clean[2:].strip()
            paragraphes.append(Paragraph(f"• {text}", normal_style))

        # Texte normal
        else:
            # Gérer le gras inline (**texte**)
            ligne_final = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', ligne_clean)

            # Gérer l'italique inline (*texte*)
            ligne_final = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', ligne_final)

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
            bottomMargin=0.5 * inch
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


def sauvegarder_rapport(contenu_original, logs_etapes, streaming_gemini, contenu_traite, debrief_correction,
                        stats_tokens=None):
    """Sauvegarde le rapport COMPLET en PDF uniquement"""
    if not contenu_traite or not contenu_traite.strip():
        log_message("⚠️ ATTENTION: Aucun contenu traité à sauvegarder")
        return None, None

    # Créer le dossier reports s'il n'existe pas
    os.makedirs("reports", exist_ok=True)

    # Générer un nom de fichier avec timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"reports/rapport_complet_{timestamp}"

    log_message(f"💾 SAUVEGARDE: Création du fichier PDF {base_filename}.pdf")

    # ÉTAPE 1: Préparer le contenu complet avec TOUS les logs
    log_message("🔧 ÉTAPE: Préparation du rapport complet...")
    contenu_final = preparer_contenu_rapport_complet(
        contenu_original=contenu_original,
        logs_etapes=logs_etapes,
        streaming_gemini=streaming_gemini,
        contenu_traite=contenu_traite,
        debrief_correction=debrief_correction,
        stats_tokens=stats_tokens
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


def ajouter_message_llm(prompt_utilisé, réponse_complète, contenu_extrait, stats_tokens):
    """Ajoute un message à l'historique LLM"""
    global historique_llm

    timestamp = datetime.now().strftime("%H:%M:%S")

    message = {
        "timestamp": timestamp,
        "prompt": prompt_utilisé,
        "réponse_complète": réponse_complète,
        "contenu_extrait": contenu_extrait,
        "stats": stats_tokens
    }

    historique_llm.append(message)


# --- Fonctions Gemini ---

GEMINI_API_KEY_PLACEHOLDER = "YOUR_GEMINI_API_KEY_HERE"


def lire_cle_api():
    """Lit la clé API dans GeminiKey.txt (ignore lignes vides et commentaires #)"""
    # utf-8-sig : tolère le BOM ajouté par le Bloc-notes Windows
    with open("GeminiKey.txt", "r", encoding="utf-8-sig") as f:
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
        log_message("❌ ÉCHEC: Fichier GeminiKey.txt introuvable")
        return None
    except Exception as e:
        log_message(f"❌ ÉCHEC: Erreur initialisation Gemini: {e}")
        return None


def lire_prompto_dys():
    """Lit le fichier prompto.dys"""
    try:
        with open("prompto.dys", "r", encoding="utf-8") as f:
            contenu = f.read()

        if "[TEXTE]" not in contenu:
            log_message("❌ ÉCHEC: Balise [TEXTE] manquante dans prompto.dys")
            return None

        return contenu
    except FileNotFoundError:
        log_message("❌ ÉCHEC: Fichier prompto.dys introuvable")
        return None
    except Exception as e:
        log_message(f"❌ ÉCHEC: Erreur lecture prompto.dys: {e}")
        return None


def extraire_contenu_note(reponse_complete):
    """Extrait le contenu entre <NOTE> et </NOTE>"""
    if "<NOTE>" in reponse_complete and "</NOTE>" in reponse_complete:
        debut = reponse_complete.find("<NOTE>") + len("<NOTE>")
        fin = reponse_complete.find("</NOTE>")
        contenu = reponse_complete[debut:fin].strip()
        # Remplacer les marqueurs __BOLD_n__ par des séparateurs horizontaux MD
        bold_count = len(re.findall(r'__BOLD_\d+__', contenu))
        if bold_count > 0:
            log_message(f"🔄 NOTE: {bold_count} marqueurs __BOLD_n__ remplacés par des séparateurs ---")
        contenu = re.sub(r'__BOLD_\d+__', '---', contenu)
        return contenu
    else:
        log_message("⚠️ ATTENTION: Balises <NOTE> absentes, utilisation complète")
        # Remplacer les marqueurs même en cas de réponse complète
        reponse_nettoyee = re.sub(r'__BOLD_\d+__', '---', reponse_complete)
        return reponse_nettoyee


def ajouter_note_origine(contenu_traite, contenu_original):
    """Ajoute la note d'origine (sans les images) à la fin de la note corrigée.
    Générée côté Python plutôt que par Gemini : copie exacte et tokens de sortie économisés."""
    if not contenu_traite.strip():
        return contenu_traite
    # Images Markdown de l'éditeur, ex. ![photo](./images/photo.png){width=300px id=...}, ou balises <img>
    note_sans_images = re.sub(r'!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?|<img[^>]*>', '', contenu_original)
    note_sans_images = re.sub(r'\n{3,}', '\n\n', note_sans_images).strip()  # Lignes vides laissées par les images
    if not note_sans_images:
        return contenu_traite
    # Retirer un éventuel séparateur final pour ne pas le doubler
    contenu_traite = re.sub(r'(\s*\n)?-{3,}\s*$', '', contenu_traite.rstrip())
    log_message(f"📎 NOTE: Note d'origine ajoutée ({len(note_sans_images)} caractères)")
    return (
        f"{contenu_traite}\n\n---\n\n"
        f"### <span style=\"color: #3399ff;\">Note d'origine</span>\n\n"
        f"{note_sans_images}\n"
    )


def extraire_debrief_correction(reponse_complete):
    """Extrait le débrief après </NOTE>"""
    if "</NOTE>" in reponse_complete:
        debut = reponse_complete.find("</NOTE>") + len("</NOTE>")
        return reponse_complete[debut:].strip()
    else:
        return ""


def traitement_gemini():
    """Traitement IA Gemini : lecture → prompt → stream → injection + CAPTURE COMPLÈTE"""
    global abandon_ia, traitement_en_cours, btn_ia_global

    # RÉINITIALISER LES LOGS ET LE FLAG D'ABANDON
    global logs_complets
    logs_complets = []
    abandon_ia = False
    traitement_en_cours = True

    log_message("\n🤖 DÉMARRAGE: TRAITEMENT IA GEMINI (ANNULABLE)")
    log_message("=" * 50)

    # VARIABLES POUR CAPTURER TOUT
    contenu_original = ""
    streaming_gemini_complet = ""
    logs_etapes_actuelles = []

    # 1. Initialiser client
    log_message("🔑 ÉTAPE 1: Initialisation du client Gemini...")
    client = init_gemini_client()
    if not client:
        log_message("❌ ÉCHEC: Impossible d'initialiser Gemini")
        return
    log_message("✅ SUCCÈS: Client Gemini initialisé")

    # 2. Lire le contenu de l'éditeur
    log_message("\n📖 ÉTAPE 2: Lecture du contenu éditeur...")
    contenu_editeur = get_markdown()
    contenu_original = contenu_editeur  # CAPTURER LE CONTENU ORIGINAL

    # Affichage console
    afficher_contenu_editeur(contenu_editeur, "📄 CONTENU LU DEPUIS L'ÉDITEUR")

    # 3. Lire le prompt template
    log_message("\n📋 ÉTAPE 3: Lecture du template prompto.dys...")
    prompt_template = lire_prompto_dys()
    if not prompt_template:
        log_message("❌ ÉCHEC: Impossible de lire prompto.dys")
        return
    log_message("✅ SUCCÈS: Template prompto.dys chargé")

    # 4. Substituer [TEXTE] et [DATE] par le contenu éditeur et la date du jour
    log_message("\n🔗 ÉTAPE 4: Préparation du prompt final...")

    # Générer la date du jour au format JJ/MM/AAAA
    date_du_jour = datetime.now().strftime("%d/%m/%Y")

    # Injecter texte + date dans le prompt
    prompt_final = (
        prompt_template
        .replace("[TEXTE]", contenu_editeur)
        .replace("[DATE]", date_du_jour)
    )

    log_message("✅ SUCCÈS: Prompt préparé (substitution [TEXTE] et [DATE] effectuée)")

    # 5. Configuration Gemini
    log_message("\n⚙️ ÉTAPE 5: Configuration des paramètres Gemini...")
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=GEMINI_THINKING_LEVEL,
            include_thoughts=True
        )
    )
    log_message(f"✅ SUCCÈS: Configuration Gemini prête (Modèle: {GEMINI_MODEL}, Thinking level: {GEMINI_THINKING_LEVEL.value})")

    # CAPTURER LES LOGS DES ÉTAPES 1-5
    logs_etapes_actuelles = logs_complets.copy()

    # 6. Streaming avec Gemini
    log_message("\n🚀 ÉTAPE 6: Envoi à Gemini et traitement en cours...")
    log_message("🔄 Streaming en direct (💭 = thinking, texte normal = réponse):")
    log_message("-" * 60)

    full_answer = ""
    last_response = None

    # Effacer la zone de texte avant de commencer
    update_streaming_text("", clear=True)

    try:
        log_message("📡 Flux IA: Démarrage de la réception des données...")
        for chunk in client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=prompt_final,
                config=config
        ):
            last_response = chunk
            # log_message("📡 Flux IA: Chunk reçu...") # Heartbeat discret

            if not chunk.candidates:
                continue
            if not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                continue

            for part in chunk.candidates[0].content.parts:
                # VÉRIFICATION DE L'ABANDON À CHAQUE CHUNK
                if abandon_ia:
                    log_message("\n🚫 ABANDON: Traitement arrêté par l'utilisateur.")
                    break

                if not part.text:
                    continue
                if part.thought:
                    thinking_text = f"💭 {part.text}"
                    log_message(thinking_text)
                    streaming_gemini_complet += thinking_text + "\n"
                else:
                    # Pour le streaming de la réponse, on affiche directement
                    log_message(part.text)
                    full_answer += part.text
                    streaming_gemini_complet += part.text
            
            if abandon_ia:
                break

    except genai_errors.ServerError as e:
        log_message(f"\n❌ ÉCHEC: Erreur serveur Gemini: {e}")
        return
    except genai_errors.APIError as e:
        log_message(f"\n❌ ÉCHEC: Erreur API Gemini: {e}")
        return
    except Exception as e:
        log_message(f"\n❌ ÉCHEC: Erreur inattendue: {e}")
        return
    finally:
        # TOUJOURS RÉINITIALISER L'ÉTAT DU BOUTON
        traitement_en_cours = False
        if btn_ia_global:
            log_message("🔄 FIN: Réinitialisation du bouton de contrôle")
            def reset_btn():
                btn_ia_global.configure(
                    text="🤖 Traiter la prise de note", 
                    state="normal"  # Rétablir l'interactivité
                )
            root_global.after(0, reset_btn)

    # VÉRIFIER SI ON A QUITTÉ À CAUSE D'UN ABANDON
    if abandon_ia:
        log_message("⚠️ INFOS: Injection et sauvegarde PDF annulées.")
        return

    log_message("\n" + "-" * 60)
    log_message("✅ SUCCÈS: Réponse Gemini complète reçue")

    # 7. Extraire le contenu entre balises NOTE
    log_message("\n🔍 ÉTAPE 7: Extraction du contenu traité...")
    contenu_traite = extraire_contenu_note(full_answer)

    if "<NOTE>" in full_answer and "</NOTE>" in full_answer:
        log_message("✅ SUCCÈS: Balises <NOTE> détectées et contenu extrait")
        log_message(f"📏 Taille du contenu traité: {len(contenu_traite)} caractères")
    else:
        log_message("⚠️ ATTENTION: Balises <NOTE> absentes, utilisation complète")

    # Section « Note d'origine » ajoutée côté Python (n'est plus générée par Gemini)
    contenu_traite = ajouter_note_origine(contenu_traite, contenu_original)

    # Extraire aussi le débrief
    debrief_correction = extraire_debrief_correction(full_answer)

    # Afficher le contenu qui va être injecté
    afficher_contenu_editeur(contenu_traite, "📄 CONTENU À INJECTER DANS L'ÉDITEUR")

    # 8. Injecter dans l'éditeur
    log_message("\n✏️ ÉTAPE 8: Injection dans l'éditeur...")
    if contenu_traite:
        success = set_markdown(contenu_traite)
        if success:
            log_message(f"✅ SUCCÈS: Contenu injecté avec succès !")
        else:
            log_message("❌ ÉCHEC: Erreur lors de l'injection dans l'éditeur")
    else:
        log_message("❌ ÉCHEC: Aucun contenu à injecter")

    # 9. Bilan des tokens
    log_message("\n📊 ÉTAPE 9: Bilan final des tokens...")
    stats_tokens = {}
    if last_response:
        usage = getattr(last_response, "usage_metadata", None)
        log_message("=" * 30)
        log_message("📊 STATISTIQUES GEMINI")
        log_message("=" * 30)
        if usage:
            stats_tokens = {
                "input": getattr(usage, "prompt_token_count", "N/A"),
                "output": getattr(usage, "candidates_token_count", "N/A"),
                "thinking": getattr(usage, "thoughts_token_count", "N/A"),
                "total": getattr(usage, "total_token_count", "N/A")
            }
            log_message(f"🔢 Input tokens     : {stats_tokens['input']}")
            log_message(f"🔢 Output tokens    : {stats_tokens['output']}")
            log_message(f"🧠 Thinking tokens  : {stats_tokens['thinking']}")
            log_message(f"🔢 Total tokens     : {stats_tokens['total']}")
        else:
            log_message("⚠️ Statistiques non disponibles pour cette réponse")
        log_message("=" * 30)

    # 10. Sauvegarde automatique PDF uniquement
    log_message("\n💾 ÉTAPE 10: Sauvegarde automatique rapport PDF...")
    md_file, pdf_file = sauvegarder_rapport(
        contenu_original=contenu_original,
        logs_etapes=logs_etapes_actuelles,
        streaming_gemini=streaming_gemini_complet,
        contenu_traite=contenu_traite,
        debrief_correction=debrief_correction,
        stats_tokens=stats_tokens
    )

    if pdf_file:
        log_message(f"🎉 SUCCÈS: Rapport PDF sauvegardé !")
        log_message(f"📁 Rapport PDF dans 'reports/'")
    else:
        log_message("⚠️ ATTENTION: Sauvegarde PDF échouée")

    # 11. Ajouter à l'historique
    ajouter_message_llm(prompt_final, full_answer, contenu_traite, stats_tokens)

    log_message("\n🎉 TERMINÉ: Traitement IA Gemini avec capture complète terminé !")


# --- GUI Tkinter avec thème Sun Valley ---
# --- Variable globale pour tracker si l'éditeur est lancé ---
editeur_lance = False
web_folder_global = None


def on_closing():
    """
    Intercepte la fermeture de la fenêtre GUI.
    Bloque la fermeture si l'éditeur est encore ouvert pour éviter la perte de données.
    L'état de l'éditeur est géré exclusivement par les callbacks React (on_editor_open/on_editor_close)
    et par le retour de eel.start() — plus fiable que la détection psutil.
    """
    global editeur_lance, root_global

    if editeur_lance:
        # Bloquer la fermeture MAIS proposer le déblocage forcé
        result = messagebox.askyesno(
            "PromptoDYS - Éditeur ouvert",
            "L'éditeur semble encore ouvert.\n\n"
            "Voulez-vous FORCER la fermeture de l'application ?\n\n"
            "⚠️ ATTENTION : Cela peut entraîner une perte de données non sauvegardées.\n\n"
            "Oui = Forcer la fermeture\n"
            "Non = Annuler et fermer d'abord l'éditeur",
            icon='warning'
        )
        if result:  # User choisit "Oui" = forcer la fermeture
            log_message("🔧 Déblocage forcé : Fermeture forcée par l'utilisateur")
            editeur_lance = False
            # Continuer vers la fermeture
        else:  # User choisit "Non" = annuler
            log_message("⚠️ Fermeture annulée : veuillez fermer l'éditeur d'abord")
            return  # Bloquer la fermeture
    
    # Pas d'éditeur ouvert, fermeture autorisée
    log_message("👋 Fermeture de l'application...")
    root_global.destroy()
    os._exit(0)  # Force la fermeture complète



# --- État de l'éditeur géré exclusivement par les callbacks React ---
# on_editor_open()  → editeur_lance = True  (React notifie l'ouverture)
# on_editor_close() → editeur_lance = False (React notifie la fermeture)
# lancer_eel()      → editeur_lance = False (eel.start() retourne/lève si crash)



def gui_control_panel():
    """
    GUI de contrôle avec Tkinter + sv_ttk (thème Windows 11)
    Panneau compact avec 3 boutons principaux
    """
    global editeur_lance, web_folder_global, root_global, status_label_global, btn_ia_global
    log_message("🖥️ Démarrage du panneau de contrôle GUI...")
    
    # --- Fonctions des boutons ---
    def btn_ouvrir_editeur():
        """Lance l'éditeur Eel dans un thread séparé"""
        global editeur_lance
        
        if editeur_lance:
            log_message("📝 L'éditeur est déjà ouvert")
            status_label.config(text="✅ L'éditeur est déjà ouvert")
            return
        
        log_message("📝 Action: Lancement de l'éditeur...")
        status_label.config(text="⏳ Ouverture de l'éditeur...")
        root.update()
        
        def lancer_eel():
            global editeur_lance
            try:
                editeur_lance = True
                eel.start('index.html',
                          mode='chrome',
                          size=(1200, 800),
                          port=8080,
                          cmdline_args=[
                              '--app=http://localhost:8080/index.html',
                              f'--user-data-dir={CHROME_PROFILE_DIR}',
                              '--disable-features=VizDisplayCompositor',
                              '--no-first-run',
                              '--no-default-browser-check',
                              '--disable-default-apps',
                              '--disable-extensions',
                              '--disable-plugins',
                              '--window-size=1200,800',
                              '--window-position=100,100'
                          ],
                          block=True)
            except Exception as e:
                log_message(f"❌ Erreur lancement éditeur: {e}")
                # Fallback
                try:
                    eel.start('index.html', mode='chrome-app', size=(1200, 800), port=8080,
                              cmdline_args=[
                                  f'--user-data-dir={CHROME_PROFILE_DIR}',
                                  '--no-first-run',
                                  '--no-default-browser-check'
                              ],
                              block=True)
                except Exception as e2:
                    log_message(f"❌ Erreur fallback: {e2}")
                    root.after(0, lambda: status_label.config(text=f"❌ Erreur: {str(e)[:20]}"))
                    editeur_lance = False
                    return
            
            # Quand l'éditeur se ferme, on met à jour le statut
            root.after(0, lambda: status_label.config(text="🔴 Éditeur fermé"))
            editeur_lance = False
        
        # Lancer dans un thread pour ne pas bloquer la GUI
        thread = threading.Thread(target=lancer_eel, daemon=True)
        thread.start()
        
        # Mettre à jour le statut après un court délai
        root.after(2000, lambda: status_label.config(text="✅ Éditeur ouvert") if editeur_lance else None)
    
    def btn_sauvegarder_document():
        """Sauvegarde le document — toujours en mode "Enregistrer sous" (dialogue à chaque fois).
        Si un document est déjà ouvert, le dialogue pré-remplit le nom et le dossier courant."""
        global editeur_lance, current_document_path
        
        if not editeur_lance:
            messagebox.showwarning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\n"
                "Veuillez d'abord ouvrir l'éditeur\n"
                "avant de sauvegarder.",
                icon='warning'
            )
            status_label.config(text="⚠️ Éditeur non ouvert")
            return
        
        log_message(f"🔍 DEBUG btn_sauvegarder: editeur_lance={editeur_lance}, current_document_path={current_document_path}")
        
        # Toujours afficher le dialogue — pré-rempli si document déjà ouvert/sauvegardé
        initial_dir = os.path.dirname(current_document_path) if current_document_path else PROMPTO_DOCS_DIR
        initial_name = os.path.basename(current_document_path) if current_document_path else "nouveau_document"
        
        selected = filedialog.asksaveasfilename(
            title="Enregistrer le document PromptoDYS...",
            initialdir=initial_dir,
            initialfile=initial_name,
            defaultextension="",
            filetypes=[("Tous les fichiers", "*.*")]
        )
        if not selected:
            log_message("💾 Sauvegarde annulée par l'utilisateur")
            return
        
        save_dir = os.path.dirname(selected)
        doc_name = os.path.splitext(os.path.basename(selected))[0]
        doc_name = re.sub(r'[<>:"/\\|?*]', '_', doc_name).strip()
        
        # Anti-récursion : si l'utilisateur a navigué à l'intérieur du dossier projet
        # (ex: PromptoDYS/equations/equations au lieu de PromptoDYS/equations)
        # on remonte au bon niveau pour éviter equations/equations/equations.md
        while os.path.basename(save_dir) == doc_name:
            log_message(f"⚠️ Anti-récursion: save_dir '{save_dir}' se termine par '{doc_name}' → on remonte")
            save_dir = os.path.dirname(save_dir)
        
        status_label.config(text="⏳ Sauvegarde en cours...")
        root.update()
        
        def run_save():
            global current_document_path
            log_message(f"🔍 DEBUG run_save: doc_name='{doc_name}', save_dir='{save_dir}'")
            result = save_document(doc_name, save_dir)
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
                ("Tous les fichiers", "*.*")
            ]
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
                # Attendre le VRAI signal de React (on_editor_open → last_editor_activity)
                # et non editeur_lance qui est mis à True trop tôt par lancer_eel()
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
            
            log_message(f"✅ Éditeur prêt, chargement du document...")
            
            result = load_document(selected_path)
            if result:
                global current_document_path
                # Mémoriser le chemin du document ouvert (comme Arduino retient le sketch ouvert)
                if selected_path.endswith(".md"):
                    current_document_path = os.path.dirname(selected_path)
                else:
                    current_document_path = selected_path
                doc_name = os.path.basename(current_document_path)
                log_message(f"📌 Document courant: {current_document_path}")
                root.after(0, lambda: status_label.config(text=f"✅ '{doc_name}' ouvert !"))
            else:
                root.after(0, lambda: status_label.config(text="❌ Erreur d'ouverture"))
        
        thread = threading.Thread(target=run_load, daemon=True)
        thread.start()
    
    def btn_traitement_ia():
        """Lance le traitement IA Gemini ou demande l'abandon"""
        global editeur_lance, traitement_en_cours, abandon_ia, btn_ia_global
        
        # SI DÉJÀ EN COURS -> DEMANDER L'ABANDON
        if traitement_en_cours:
            log_message("🚫 Action: Demande d'abandon du traitement IA...")
            abandon_ia = True
            btn_ia.configure(text="⏳ Abandon en cours...", state="disabled")
            
            # FAILSAFE UI: Forcer le reset du bouton après 5s quoi qu'il arrive
            def failsafe_reset():
                global traitement_en_cours
                if traitement_en_cours or btn_ia.cget("text") == "⏳ Abandon en cours...":
                    log_message("⚠️ FAILSAFE: Déblocage forcé de l'interface (reset bouton)")
                    traitement_en_cours = False
                    btn_ia.configure(text="🤖 Traiter la prise de note", style="Big.TButton", state="normal")
            
            root.after(5000, failsafe_reset)
            return

        # VÉRIFICATION 1: Connexion internet - SUPPRIMÉE
        log_message("\n🔍 VÉRIFICATION PRÉ-TRAITEMENT IA...")
        
        # VÉRIFICATION 2: Éditeur ouvert
        if not editeur_lance:
            log_message("⚠️ L'éditeur n'est pas ouvert !")
            messagebox.showwarning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\n"
                "Veuillez d'abord ouvrir l'éditeur\n"
                "avant de lancer le traitement IA.",
                icon='warning'
            )
            status_label.config(text="⚠️ Éditeur non ouvert")
            return
        
        log_message("🤖 Action: Lancement du traitement IA...")
        status_label.config(text="⏳ Traitement IA en cours...")
        
        # Mise à jour du bouton en mode "Abandon"
        btn_ia.configure(text="⛔ Abandonner le traitement")
        root.update()
        
        # Lancer le traitement dans un thread pour ne pas bloquer la GUI
        def run_traitement():
            try:
                traitement_gemini()
                # Mise à jour du statut après traitement (thread-safe)
                if not abandon_ia:
                    root.after(0, lambda: status_label.config(text="✅ Traitement IA terminé !"))
                else:
                    root.after(0, lambda: status_label.config(text="🚫 Traitement annulé"))
            except Exception as e:
                log_message(f"❌ Erreur critique IA: {e}")
                root.after(0, lambda: status_label.config(text=f"❌ Erreur: {str(e)[:30]}"))
        
        thread = threading.Thread(target=run_traitement, daemon=True)
        thread.start()
    
    def btn_ouvrir_rapports():
        """Ouvre le dossier des rapports PDF dans l'explorateur Windows"""
        log_message("📂 Action: Ouverture du dossier reports...")
        reports_path = os.path.abspath("reports")
        
        # Créer le dossier s'il n'existe pas
        os.makedirs(reports_path, exist_ok=True)
        
        # Ouvrir le dossier dans l'explorateur Windows
        try:
            subprocess.Popen(f'explorer "{reports_path}"')
            status_label.config(text=f"📂 Dossier reports ouvert")
        except Exception as e:
            status_label.config(text=f"❌ Erreur ouverture: {str(e)[:20]}")
            log_message(f"❌ Erreur ouverture dossier: {e}")
    
    def btn_quitter():
        """Ferme l'application complète"""
        # Réutiliser la fonction on_closing pour la cohérence
        on_closing()
    
    # --- Création de la fenêtre principale ---
    root = tk.Tk()
    root_global = root  # Référence globale pour les callbacks Eel
    root.title("PromptoDYS - Panneau de Contrôle")
    root.geometry("688x1100")  # Largeur 688px, hauteur 1100px
    root.configure(bg="#F3F3F3")  # Fond gris
    root.resizable(True, True)  # Fenêtre redimensionnable
    
    # Intercepter la fermeture de la fenêtre (X rouge)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.minsize(550, 1000)  # Taille minimale ajustée
    
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
    
    # --- Frame principal avec padding ---
    main_frame = ttk.Frame(root, padding=(20, 20, 20, 0), style="Gray.TFrame")  # Fond gris, pas de padding en bas
    main_frame.pack(fill="both", expand=True)
    
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
        font=("Segoe UI", 24, "bold")  # Réduit de 32 à 24
    )
    title_label.pack(side="left")
    
    
    
    # --- Fonctions pour effets de survol sur boutons tk.Button ---
    def on_button_enter(event, btn):
        """Effet au survol : bordure bleue, fond bleu clair, texte bleu"""
        btn.config(
            bg="#E3F2FD",  # Fond bleu clair
            fg="#0078D4",  # Texte bleu
            highlightbackground="#0078D4",  # Bordure bleue
            highlightthickness=12  # Bordure épaisse au survol
        )
    
    def on_button_leave(event, btn):
        """Retour à l'état normal"""
        btn.config(
            bg="#FFFFFF",  # Fond blanc
            fg="#1F1F1F",  # Texte noir
            highlightbackground="#333333",  # Bordure sombre
            highlightthickness=12  # Bordure épaisse maintenue
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
        cursor="hand2"
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
        cursor="hand2"
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
        cursor="hand2"
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
        cursor="hand2"
    )
    btn_ia.pack(pady=8, fill="x", padx=20)
    btn_ia.bind("<Enter>", lambda e: on_button_enter(e, btn_ia))
    btn_ia.bind("<Leave>", lambda e: on_button_leave(e, btn_ia))
    btn_ia.bind("<ButtonPress-1>", lambda e: on_button_press(e, btn_ia))
    btn_ia.bind("<ButtonRelease-1>", lambda e: on_button_release(e, btn_ia))
    btn_ia_global = btn_ia  # Garder la référence globale

    
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
        cursor="hand2"
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
        font=("Segoe UI", 14)  # Réduit de 18 à 14
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
        font=("Consolas", 10), # Police légèrement plus petite pour logs
        wrap="word",
        state="disabled",  # Lecture seule
        bg="#f8f8f8",
        fg="#333333"
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
        cursor="hand2"
    )
    btn_quit.pack(pady=0)  # Aucune marge
    # Effets de survol spécifiques pour le bouton Quitter
    btn_quit.bind("<Enter>", lambda e: btn_quit.config(bg="#FFE6E6", fg="#CC0000", highlightbackground="#CC0000"))
    btn_quit.bind("<Leave>", lambda e: btn_quit.config(bg="#F5F5F5", fg="#666666", highlightbackground="#999999"))
    
    # --- Lancer la boucle principale ---
    print("✅ Panneau de contrôle GUI prêt !")
    root.mainloop()


def main():
    """Lance l'application - GUI d'abord, éditeur via bouton"""
    global web_folder_global
    
    log_message('🚀 Lancement de PromptoDYS...')
    log_message('💾 Sauvegarde automatique : PDF uniquement avec CAPTURE COMPLÈTE des logs')

    # Trouver le dossier web
    web_folder_global = find_web_folder()
    if not web_folder_global:
        log_message("💡 Placez votre build React dans le dossier 'build/'")
        return

    # Créer le dossier reports
    os.makedirs("reports", exist_ok=True)
    log_message('📁 Dossier "reports" créé pour les sauvegardes automatiques')

    # Initialiser Eel (préparation, mais ne lance pas encore)
    eel.init(web_folder_global)
    log_message('✅ Eel initialisé, prêt à lancer l\'éditeur')

    # Lancer la GUI de contrôle (BLOQUANT - boucle principale)
    log_message('🖥️ Lancement du panneau de contrôle...')
    gui_control_panel()

    log_message("🔚 Application fermée")


if __name__ == '__main__':
    main()
