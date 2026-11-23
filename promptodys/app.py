"""Assemblage de PromptoDYS : main() relie les trois couches et lance le panneau de contrôle.

Seul module qui connaît à la fois le domaine, l'infrastructure et la présentation. Aucune couche
ne l'importe (contrat import-linter).

- main() : point d'entrée (askGeminiPrompto.py, python -m promptodys, exe PyInstaller) ;
- run_processing() : traitement IA complet, étapes 1, 2 et 9 autour du cas d'usage process_note().

Les destinations des logs (console, terminal, fichier, rapport PDF) sont décrites dans
promptodys/infrastructure/logs.py.
"""

import contextlib
import functools
import logging
import os
import queue
import sys
import threading
from datetime import datetime

from promptodys.domain import ports, processing
from promptodys.infrastructure import config, disk_document_store, eel_editor, gemini_model, logs, pdf_report
from promptodys.presentation.control_panel import ControlPanel
from promptodys.presentation.panel_controller import PanelController

_logger = logging.getLogger(__name__)

# --- Traitement IA ---


def run_processing(editor: ports.Editor, cancel: threading.Event) -> bool:
    """Traitement IA Gemini : client → modèle de prompt → cas d'usage processing.process_note → rapport PDF

    cancel : threading.Event propre à ce traitement, déclenché par le bouton « Abandonner ».
    Un traitement abandonné s'arrête à la sortie du flux, sans rien écrire dans l'éditeur ni le PDF.

    Les logs émis pendant le traitement par ce thread (sauf les morceaux du flux de l'IA) sont
    recueillis par un ReportLogCollector pour la section des logs du rapport PDF.

    Renvoie True si le traitement est allé jusqu'au bout, False en cas d'échec ou d'abandon.
    """
    with logs.ReportLogCollector() as collector:
        _logger.info("\n🤖 DÉMARRAGE: TRAITEMENT IA GEMINI (ANNULABLE)")
        _logger.info("=" * 50)

        # 1. Initialiser le client et sa configuration
        _logger.info("🔑 ÉTAPE 1: Initialisation du client Gemini...")
        client = gemini_model.create_client()
        if not client:
            _logger.error("❌ ÉCHEC: Impossible d'initialiser Gemini")
            return False
        model = gemini_model.GeminiModel(client)
        _logger.info(
            f"✅ SUCCÈS: Client Gemini initialisé (Modèle: {config.GEMINI_MODEL}, "
            f"Thinking level: {config.GEMINI_THINKING_LEVEL.value})"
        )

        # 2. Lire le modèle de prompt
        _logger.info("\n📋 ÉTAPE 2: Lecture du template promptodys.prompt...")
        prompt_template = config.read_prompt_template()
        if not prompt_template:
            _logger.error("❌ ÉCHEC: Impossible de lire promptodys.prompt")
            return False
        _logger.info("✅ SUCCÈS: Template promptodys.prompt chargé")

        # 3 à 8. Lecture de l'éditeur, prompt, flux IA, extraction, injection, jetons
        result = processing.process_note(editor, model, prompt_template, cancel, datetime.now().date())
        if result.status is not processing.ProcessingStatus.COMPLETED:
            return False

        # 9. Sauvegarde automatique PDF uniquement
        _logger.info("\n💾 ÉTAPE 9: Sauvegarde automatique rapport PDF...")
        pdf_file = pdf_report.save_report(
            original_note=result.original_note,
            # Copie : les logs de la génération du PDF elle-même n'y entrent pas
            step_logs=list(collector.messages),
            ai_stream=result.ai_stream,
            processed_note=result.processed_note,
            correction_debrief=result.correction_debrief,
            token_stats=result.token_stats,
        )

        if pdf_file:
            _logger.info("🎉 SUCCÈS: Rapport PDF sauvegardé !")
            _logger.info(f"📁 Rapport PDF dans {config.REPORTS_DIR}")
        else:
            _logger.error("❌ ÉCHEC: Sauvegarde PDF échouée")

        _logger.info("\n🎉 TERMINÉ: Traitement IA Gemini avec capture complète terminé !")
        return True


# --- Point d'entrée ---


def main() -> None:
    """Lance l'application - GUI d'abord, éditeur via bouton"""
    # Avant la création de la fenêtre Tk, sinon l'interface est floue sous Windows
    if sys.platform == "win32":
        import ctypes

        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # DPI per monitor

    # Avant le premier log. Les logs destinés à la console attendent dans la file que le panneau la lise
    console_queue: queue.Queue[logging.LogRecord] = queue.Queue()
    logs.configure(config.LOGS_DIR, console_queue)
    _logger.info("🚀 Lancement de PromptoDYS...")
    _logger.info(f"📝 Journal de l'application : {os.path.join(config.LOGS_DIR, logs.LOG_FILE_NAME)}")

    # Trouver le dossier web
    web_folder = config.find_web_folder()
    if not web_folder:
        _logger.error("❌ Éditeur introuvable : placez le build React dans le dossier 'build_web/'")
        return

    # Créer le dossier reports
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    _logger.info(f"📁 Dossier des rapports PDF : {config.REPORTS_DIR}")

    # Créer le dossier des documents et le profil Chrome de l'éditeur
    os.makedirs(config.PROMPTO_DOCS_DIR, exist_ok=True)
    _logger.info(f"📁 Dossier projets PromptoDYS : {config.PROMPTO_DOCS_DIR}")
    os.makedirs(config.CHROME_PROFILE_DIR, exist_ok=True)
    _logger.info(f"🌐 Profil Chrome PromptoDYS : {config.CHROME_PROFILE_DIR}")

    # Initialiser Eel (préparation, mais ne lance pas encore)
    eel_editor.init(web_folder)
    _logger.info("✅ Eel initialisé, prêt à lancer l'éditeur")

    # Construire le panneau de contrôle (la vue) et son contrôleur, puis transmettre au contrôleur
    # les clics du panneau et les événements de React. Le contrôleur est construit ici, sur le thread
    # de l'interface : c'est le seul autorisé à modifier son état.
    _logger.info("🖥️ Lancement du panneau de contrôle...")
    panel = ControlPanel(
        reports_dir=config.REPORTS_DIR,
        icon_path=os.path.join(config.RESOURCES_DIR, "assets", "prompto.png"),
        log_queue=console_queue,
    )
    editor = eel_editor.EelEditor()
    controller = PanelController(
        view=panel,
        editor=editor,
        store=disk_document_store.DiskDocumentStore(),
        editor_window=eel_editor.EelWindow(config.EEL_PORT, config.CHROME_PROFILE_DIR),
        process_note=functools.partial(run_processing, editor),
        documents_dir=config.PROMPTO_DOCS_DIR,
    )
    panel.set_controller(controller)
    eel_editor.set_event_handlers(controller.on_editor_open, controller.on_editor_close)

    # Lancer la GUI de contrôle (BLOQUANT - boucle principale)
    panel.run()

    _logger.info("🔚 Application fermée")
