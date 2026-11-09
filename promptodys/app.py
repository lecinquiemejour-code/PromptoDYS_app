"""Assemblage de PromptoDYS : main() relie les trois couches et lance le panneau de contrôle.

Seul module qui connaît à la fois le domaine, l'infrastructure et la présentation. Aucune couche
ne l'importe (contrat import-linter).

- main() : point d'entrée (askGeminiPrompto.py, python -m promptodys, exe PyInstaller) ;
- run_processing() : traitement IA complet, étapes 1, 2 et 9 autour du cas d'usage process_note() ;
- report_logs, log_message(), LogMessageHandler, configure_logger() : journalisation provisoire, jusqu'à R7.
"""

import contextlib
import functools
import logging
import os
import sys
import threading
from datetime import datetime

from promptodys.domain import ports, processing
from promptodys.infrastructure import config, disk_document_store, eel_editor, gemini_model, pdf_report
from promptodys.presentation.control_panel import ControlPanel

# --- Journalisation provisoire (remplacée par les handlers de logging avec R7) ---

# Logs du traitement IA en cours, copiés dans le rapport PDF
report_logs: list[str] = []


def log_message(message: str) -> None:
    """Log un message dans la console ET le capture pour les rapports"""
    print(message, flush=True)
    # Les prints sont maintenant redirigés vers la GUI via stdout mais on garde l'ajout explicite aux logs complets
    # Capturer aussi dans les logs complets
    report_logs.append(message)


class LogMessageHandler(logging.Handler):
    """Pont provisoire : renvoie les logs du paquet vers log_message (console, GUI, rapport).
    Sera remplacé par les vrais handlers de logging avec R7."""

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            log_message(self.format(record))


def configure_logger() -> None:
    """Envoie les logs du paquet promptodys vers log_message, message seul (sans niveau ni heure).
    Appelée par main(), jamais à l'import : les tests gardent la configuration de logging par défaut."""
    logger = logging.getLogger("promptodys")
    logger.setLevel(logging.INFO)
    logger.addHandler(LogMessageHandler())
    logger.propagate = False  # pas de second affichage par le logger racine


# --- Traitement IA ---


def run_processing(editor: ports.Editor, cancel: threading.Event) -> bool:
    """Traitement IA Gemini : client → modèle de prompt → cas d'usage processing.process_note → rapport PDF

    cancel : threading.Event propre à ce traitement, déclenché par le bouton « Abandonner ».
    Un traitement abandonné s'arrête à la sortie du flux, sans rien écrire dans l'éditeur ni le PDF.

    Renvoie True si le traitement est allé jusqu'au bout, False en cas d'échec ou d'abandon.
    """
    # Nouveau traitement : logs du rapport vidés AVANT le premier log
    # (la console, elle, est vidée par le panneau juste avant le lancement du traitement)
    report_logs.clear()

    log_message("\n🤖 DÉMARRAGE: TRAITEMENT IA GEMINI (ANNULABLE)")
    log_message("=" * 50)

    # 1. Initialiser le client et sa configuration
    log_message("🔑 ÉTAPE 1: Initialisation du client Gemini...")
    client = gemini_model.create_client()
    if not client:
        log_message("❌ ÉCHEC: Impossible d'initialiser Gemini")
        return False
    model = gemini_model.GeminiModel(client)
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
    logs_before_processing = report_logs.copy()

    # 3 à 8. Lecture de l'éditeur, prompt, flux IA, extraction, injection, jetons
    result = processing.process_note(editor, model, prompt_template, cancel, datetime.now().date())
    if result.status is not processing.ProcessingStatus.COMPLETED:
        return False

    # 9. Sauvegarde automatique PDF uniquement
    log_message("\n💾 ÉTAPE 9: Sauvegarde automatique rapport PDF...")
    pdf_file = pdf_report.save_report(
        original_note=result.original_note,
        step_logs=logs_before_processing + result.step_logs,
        ai_stream=result.ai_stream,
        processed_note=result.processed_note,
        correction_debrief=result.correction_debrief,
        token_stats=result.token_stats,
    )

    if pdf_file:
        log_message("🎉 SUCCÈS: Rapport PDF sauvegardé !")
        log_message(f"📁 Rapport PDF dans {config.REPORTS_DIR}")
    else:
        log_message("⚠️ ATTENTION: Sauvegarde PDF échouée")

    log_message("\n🎉 TERMINÉ: Traitement IA Gemini avec capture complète terminé !")
    return True


# --- Point d'entrée ---


def main() -> None:
    """Lance l'application - GUI d'abord, éditeur via bouton"""
    # Avant la création de la fenêtre Tk, sinon l'interface est floue sous Windows
    if sys.platform == "win32":
        import ctypes

        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # DPI per monitor

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
    editor = eel_editor.EelEditor()
    panel = ControlPanel(
        editor=editor,
        store=disk_document_store.DiskDocumentStore(),
        editor_window=eel_editor.EelWindow(config.EEL_PORT, config.CHROME_PROFILE_DIR),
        process_note=functools.partial(run_processing, editor),
        documents_dir=config.PROMPTO_DOCS_DIR,
        reports_dir=config.REPORTS_DIR,
        icon_path=os.path.join(config.RESOURCES_DIR, "assets", "prompto.png"),
    )
    eel_editor.set_event_handlers(panel.on_editor_open, panel.on_editor_close)

    # Lancer la GUI de contrôle (BLOQUANT - boucle principale)
    panel.run()

    log_message("🔚 Application fermée")
