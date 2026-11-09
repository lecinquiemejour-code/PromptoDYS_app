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
import logging
import os
from datetime import datetime

# --- Couche domaine (règles pures, voir promptodys/) ---
from promptodys.domain import processing

# --- Couche infrastructure (adaptateurs, configuration) ---
from promptodys.infrastructure import config, disk_document_store, eel_editor, gemini_model, pdf_report

# --- Couche présentation (panneau de contrôle Tkinter) ---
from promptodys.presentation.control_panel import ControlPanel

# --- NOUVELLE VARIABLE POUR CAPTURER TOUS LES LOGS ---
logs_complets = []


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


# Éditeur utilisé par le traitement IA et par le panneau (aucun effet de bord à la construction)
editeur_eel = eel_editor.EelEditor()


# --- Fonctions Gemini ---


def traitement_gemini(annulation):
    """Traitement IA Gemini : client → modèle de prompt → cas d'usage processing.process_note → rapport PDF

    annulation : threading.Event propre à ce traitement, déclenché par le bouton « Abandonner ».
    Un traitement abandonné s'arrête à la sortie du flux, sans rien écrire dans l'éditeur ni le PDF.

    Renvoie True si le traitement est allé jusqu'au bout, False en cas d'échec ou d'abandon.
    """
    # Nouveau traitement : logs du rapport vidés AVANT le premier log
    # (la console, elle, est vidée par le panneau juste avant le lancement du traitement)
    global logs_complets
    logs_complets = []

    log_message("\n🤖 DÉMARRAGE: TRAITEMENT IA GEMINI (ANNULABLE)")
    log_message("=" * 50)

    # 1. Initialiser le client et sa configuration
    log_message("🔑 ÉTAPE 1: Initialisation du client Gemini...")
    client = gemini_model.create_client()
    if not client:
        log_message("❌ ÉCHEC: Impossible d'initialiser Gemini")
        return False
    modele = gemini_model.GeminiModel(client)
    log_message(
        f"✅ SUCCÈS: Client Gemini initialisé (Modèle: {config.GEMINI_MODEL}, "
        f"Thinking level: {config.GEMINI_THINKING_LEVEL.value})"
    )

    # 2. Lire le modèle de prompt
    log_message("\n📋 ÉTAPE 2: Lecture du template promptodys.prompt...")
    prompt_template = config.read_prompt_template()
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
    pdf_file = pdf_report.save_report(
        original_note=resultat.original_note,
        step_logs=logs_avant_traitement + resultat.step_logs,
        ai_stream=resultat.ai_stream,
        processed_note=resultat.processed_note,
        correction_debrief=resultat.correction_debrief,
        token_stats=resultat.token_stats,
    )

    if pdf_file:
        log_message("🎉 SUCCÈS: Rapport PDF sauvegardé !")
        log_message(f"📁 Rapport PDF dans {config.REPORTS_DIR}")
    else:
        log_message("⚠️ ATTENTION: Sauvegarde PDF échouée")

    log_message("\n🎉 TERMINÉ: Traitement IA Gemini avec capture complète terminé !")
    return True


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
    web_folder = config.find_web_folder()
    if not web_folder:
        log_message("💡 Placez votre build React dans le dossier 'build/'")
        return

    # Créer le dossier reports
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    log_message(f"📁 Dossier des rapports PDF : {config.REPORTS_DIR}")

    # Créer le dossier des documents et le profil Chrome de l'éditeur
    os.makedirs(config.PROMPTO_DOCS_DIR, exist_ok=True)
    log_message(f"📁 Dossier projets PromptoDYS : {config.PROMPTO_DOCS_DIR}")
    os.makedirs(config.CHROME_PROFILE_DIR, exist_ok=True)
    log_message(f"🌐 Profil Chrome PromptoDYS : {config.CHROME_PROFILE_DIR}")

    # Initialiser Eel (préparation, mais ne lance pas encore)
    eel_editor.init(web_folder)
    log_message("✅ Eel initialisé, prêt à lancer l'éditeur")

    # Construire le panneau de contrôle, puis lui transmettre les événements de React
    log_message("🖥️ Lancement du panneau de contrôle...")
    panel = ControlPanel(
        editor=editeur_eel,
        store=disk_document_store.DiskDocumentStore(),
        editor_window=eel_editor.EelWindow(config.EEL_PORT, config.CHROME_PROFILE_DIR),
        process_note=traitement_gemini,
        documents_dir=config.PROMPTO_DOCS_DIR,
        reports_dir=config.REPORTS_DIR,
        icon_path=os.path.join(config.RESOURCES_DIR, "assets", "prompto.png"),
    )
    eel_editor.set_event_handlers(panel.on_editor_open, panel.on_editor_close)

    # Lancer la GUI de contrôle (BLOQUANT - boucle principale)
    panel.run()

    log_message("🔚 Application fermée")


if __name__ == "__main__":
    main()
