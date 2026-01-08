#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Python unifié pour l'éditeur Markdown avec intégration Eel + IA Gemini
Combinaison : Interface desktop + Assistant IA pour traitement de texte

GUI de contrôle avec Tkinter + sv_ttk (thème Sun Valley Windows 11)

Installation requise:
pip install eel google-genai reportlab markdown
Usage:
python PromptoDYS.py

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
import markdown
import re

# --- Imports pour PDF avec reportlab (remplace weasyprint) ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents

# --- Imports Gemini ---
from google import genai
from google.genai import types
import google.genai.errors as genai_errors

# --- Imports GUI Tkinter + sv_ttk ---
import tkinter as tk
from tkinter import ttk
import sv_ttk  # Thème Sun Valley (Windows 11 look)
import subprocess  # Pour ouvrir le dossier reports

try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)  # DPI per monitor
except:
    pass  # Ignorer si non Windows


# --- Historique des messages LLM ---
historique_llm = []

# --- NOUVELLE VARIABLE POUR CAPTURER TOUS LES LOGS ---
logs_complets = []



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
    global editeur_lance, root_global, status_label_global
    editeur_lance = True
    print("✅ Éditeur ouvert (notifié par React)")
    # Mettre à jour la GUI si disponible
    if root_global and status_label_global:
        root_global.after(0, lambda: status_label_global.config(text="✅ Éditeur ouvert"))


@eel.expose
def on_editor_close():
    """Appelé par React avant la fermeture de la fenêtre"""
    global editeur_lance, root_global, status_label_global
    editeur_lance = False
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
    contenu_final += f"- **Modèle IA :** Gemini 2.5 Flash\n"
    contenu_final += f"- **Mode :** Thinking activé\n"
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

def init_gemini_client():
    """Initialise le client Gemini avec la clé API"""
    try:
        with open("GeminiKey.txt", "r") as f:
            api_key = f.readline().strip()
            log_message(f"🔑 INFO: Clé API chargée ({api_key[:10]}...)")
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


def extraire_debrief_correction(reponse_complete):
    """Extrait le débrief après </NOTE>"""
    if "</NOTE>" in reponse_complete:
        debut = reponse_complete.find("</NOTE>") + len("</NOTE>")
        return reponse_complete[debut:].strip()
    else:
        return ""


def traitement_gemini():
    """Traitement IA Gemini : lecture → prompt → stream → injection + CAPTURE COMPLÈTE"""

    # RÉINITIALISER LES LOGS POUR CETTE SESSION
    global logs_complets
    logs_complets = []

    log_message("\n🤖 DÉMARRAGE: TRAITEMENT IA GEMINI AVEC CAPTURE COMPLÈTE")
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
        temperature=0.0,  # Cohérence pour corrections
        max_output_tokens=None
    )

    # Thinking activé
    config.thinking_config = types.ThinkingConfig(
        thinking_budget=500,
        include_thoughts=True
    )
    log_message("✅ SUCCÈS: Configuration Gemini prête (thinking activé)")

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
        for chunk in client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=prompt_final,
                config=config
        ):
            last_response = chunk

            if not chunk.candidates:
                continue
            if not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                continue

            for part in chunk.candidates[0].content.parts:
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

    except genai_errors.ServerError as e:
        log_message(f"\n❌ ÉCHEC: Erreur serveur Gemini: {e}")
        return
    except genai_errors.APIError as e:
        log_message(f"\n❌ ÉCHEC: Erreur API Gemini: {e}")
        return
    except Exception as e:
        log_message(f"\n❌ ÉCHEC: Erreur inattendue: {e}")
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


# --- Fonctions Console ---

def lire_contenu():
    """Interface console pour lire le contenu"""
    log_message("\n🔍 ÉTAPE: LECTURE du contenu actuel...")
    contenu = get_markdown()
    afficher_contenu_editeur(contenu)


def ecrire_contenu():
    """Interface console pour écrire du contenu"""
    log_message("\n✏️ ÉTAPE: ÉCRITURE dans l'éditeur...")
    log_message("💡 Tapez votre contenu Markdown (lignes multiples autorisées)")
    log_message("💡 Tapez 'EOF' sur une ligne vide pour terminer")
    log_message("-" * 50)

    lignes = []
    while True:
        try:
            ligne = input()
            if ligne.strip().upper() == "EOF":
                break
            lignes.append(ligne)
        except KeyboardInterrupt:
            log_message("\n❌ SAISIE ANNULÉE")
            return

    contenu = "\n".join(lignes)

    if contenu.strip():
        # Afficher le contenu qui va être injecté
        afficher_contenu_editeur(contenu, "📄 CONTENU À INJECTER")

        log_message("\n✏️ INJECTION dans l'éditeur...")
        success = set_markdown(contenu)
        if success:
            log_message("✅ SUCCÈS: Contenu injecté avec succès !")
        else:
            log_message("❌ ÉCHEC: Erreur lors de l'injection")
    else:
        log_message("❌ ÉCHEC: Contenu vide, rien à injecter")


def menu_console():
    """Menu console qui s'exécute en parallèle (OBSOLÈTE - remplacé par GUI)"""
    # Attendre que l'éditeur soit prêt
    log_message("⏳ Attente que l'éditeur soit prêt...")
    time.sleep(5)

    log_message("\n" + "=" * 50)
    log_message("🎮 ÉDITEUR MARKDOWN + IA GEMINI")
    log_message("💾 Sauvegarde automatique: PDF uniquement (CAPTURE COMPLÈTE)")
    log_message("🔧 PDF généré avec reportlab + TOUS LES LOGS")
    log_message("=" * 50)

    while True:
        try:
            log_message(f"\n📋 Options:")
            log_message(f"  1 - Lire le contenu de l'éditeur")
            log_message(f"  2 - Écrire dans l'éditeur")
            log_message(f"  3 - 🤖 Traitement de la note par l'IA de PromptoDYS")
            log_message(f"  0 - Quitter")
            log_message("-" * 30)

            choix = input("🎯 Votre choix (1/2/3/0): ").strip()

            if choix == "1":
                lire_contenu()

            elif choix == "2":
                ecrire_contenu()

            elif choix == "3":
                traitement_gemini()

            elif choix == "0":
                log_message("\n👋 Fermeture...")
                os._exit(0)  # Forcer la fermeture complète

            else:
                log_message("❌ Choix invalide. Utilisez 1, 2, 3 ou 0")

        except KeyboardInterrupt:
            log_message("\n\n👋 Au revoir !")
            os._exit(0)
        except Exception as e:
            log_message(f"❌ Erreur: {e}")


# --- GUI Tkinter avec thème Sun Valley ---
# --- Variable globale pour tracker si l'éditeur est lancé ---
editeur_lance = False
web_folder_global = None


def gui_control_panel():
    """
    GUI de contrôle avec Tkinter + sv_ttk (thème Windows 11)
    Panneau compact avec 3 boutons principaux
    """
    global editeur_lance, web_folder_global, root_global, status_label_global
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
                              '--disable-web-security',
                              '--disable-features=VizDisplayCompositor',
                              '--no-first-run',
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
                    eel.start('index.html', mode='chrome-app', size=(1200, 800), port=8080, block=True)
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
    
    def btn_traitement_ia():
        """Lance le traitement IA Gemini dans un thread séparé"""
        global editeur_lance
        
        # Vérifier si l'éditeur est ouvert
        if not editeur_lance:
            log_message("⚠️ L'éditeur n'est pas ouvert !")
            status_label.config(text="⚠️ Ouvrez l'éditeur d'abord !")
            return
        
        log_message("🤖 Action: Lancement du traitement IA...")
        status_label.config(text="⏳ Traitement IA en cours...")
        root.update()  # Rafraîchir l'interface
        
        # Lancer le traitement dans un thread pour ne pas bloquer la GUI
        def run_traitement():
            try:
                traitement_gemini()
                # Mise à jour du statut après traitement (thread-safe)
                root.after(0, lambda: status_label.config(text="✅ Traitement IA terminé !"))
            except Exception as e:
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
        log_message("👋 Fermeture de l'application...")
        root.destroy()
        os._exit(0)  # Fermer aussi Eel
    
    # --- Création de la fenêtre principale ---
    root = tk.Tk()
    root_global = root  # Référence globale pour les callbacks Eel
    root.title("PromptoDYS - Panneau de Contrôle")
    root.geometry("860x880")  # Taille optimale
    root.resizable(True, True)  # Fenêtre redimensionnable
    root.minsize(700, 700)  # Taille minimale
    
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
    
    # --- Frame principal avec padding ---
    main_frame = ttk.Frame(root, padding=20)  # Réduit de 40 à 20
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
    
    
    
    # --- Style personnalisé pour les boutons avec bordures saillantes ---
    style = ttk.Style()
    style.configure("Big.TButton", font=("Segoe UI", 16), padding=15, relief="raised", borderwidth=3)
    style.map("Big.TButton",
              relief=[("pressed", "sunken"), ("!pressed", "raised")],
              bordercolor=[("focus", "#0078D4"), ("!focus", "#666666")])
    
    # --- Boutons ---
    # Bouton 1: Ouvrir l'éditeur
    btn1 = ttk.Button(
        main_frame,
        text="📝 Ouvrir l'Éditeur",
        command=btn_ouvrir_editeur,
        width=40,
        style="Big.TButton"
    )
    btn1.pack(pady=5, ipady=5)  # Réduit de 10 à 5
    
    # Bouton 2: Traitement IA
    btn2 = ttk.Button(
        main_frame,
        text="🤖 Traiter la prise de note",
        command=btn_traitement_ia,
        width=40,
        style="Big.TButton"
    )
    btn2.pack(pady=5, ipady=5)  # Réduit de 10 à 5
    
    # Bouton 3: Ouvrir rapports PDF
    btn3 = ttk.Button(
        main_frame,
        text="📂 Voir les rapports PDF",
        command=btn_ouvrir_rapports,
        width=40,
        style="Big.TButton"
    )
    btn3.pack(pady=5, ipady=5)  # Réduit de 10 à 5
    
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
    style.configure("Quit.TButton", font=("Segoe UI", 14), padding=10)
    btn_quit = ttk.Button(
        main_frame,
        text="❌ Quitter",
        command=btn_quitter,
        width=20,
        style="Quit.TButton"
    )
    btn_quit.pack(pady=(10, 0))
    
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
