import io
import logging
import queue
import sys
import threading

import pytest

from promptodys.domain import log_marks, processing
from promptodys.infrastructure import logs


@pytest.fixture
def configured(tmp_path, monkeypatch):
    """Appelle logs.configure() vers un dossier temporaire et un faux terminal, puis rétablit
    la configuration globale (handlers, niveaux, stderr, excepthooks)."""
    root = logging.getLogger()
    package = logging.getLogger("promptodys")
    saved_levels = (root.level, package.level)
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(package, "handlers", [])
    monkeypatch.setattr(package, "propagate", package.propagate)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)

    console = queue.Queue()
    terminal = io.StringIO()
    log_dir = tmp_path / "logs"
    logs.configure(str(log_dir), console, terminal)
    # Gardé tout de suite : pendant le test, pytest remplace sys.stderr pour capturer la sortie
    stderr = sys.stderr

    class Configured:
        stderr_stream = stderr

        def __init__(self):
            self.console = console

        def console_messages(self):
            messages = []
            while not console.empty():
                messages.append(console.get_nowait().getMessage())
            return messages

        def terminal_text(self):
            return terminal.getvalue()

        def file_text(self):
            return (log_dir / logs.LOG_FILE_NAME).read_text(encoding="utf-8")

    yield Configured()

    # Fichier fermé avant la suppression du dossier temporaire (verrou sous Windows)
    for handler in root.handlers + package.handlers:
        handler.close()
    logging.captureWarnings(False)
    # setLevel (et non une simple affectation) vide le cache des niveaux des loggers
    root.setLevel(saved_levels[0])
    package.setLevel(saved_levels[1])


def test_configure_creates_log_dir(tmp_path, configured):
    assert (tmp_path / "logs").is_dir()


def test_debug_goes_to_file_and_terminal_not_console(configured):
    logging.getLogger("promptodys.domain.note").debug("🔍 détail")

    assert configured.console_messages() == []
    assert "DEBUG promptodys.domain.note : 🔍 détail" in configured.file_text()
    assert "DEBUG   🔍 détail" in configured.terminal_text()


def test_info_warning_error_go_everywhere(configured):
    logger = logging.getLogger("promptodys.app")
    logger.info("✅ info")
    logger.warning("⚠️ attention")
    logger.error("❌ erreur")

    assert configured.console_messages() == ["✅ info", "⚠️ attention", "❌ erreur"]
    file_text = configured.file_text()
    assert "INFO promptodys.app : ✅ info" in file_text
    assert "WARNING promptodys.app : ⚠️ attention" in file_text
    assert "ERROR promptodys.app : ❌ erreur" in file_text
    assert "ERROR   ❌ erreur" in configured.terminal_text()


def test_console_receives_section_mark(configured):
    """La marque SECTION arrive jusqu'à la console, qui s'en sert pour insérer une ligne vide."""
    logging.getLogger("promptodys.app").info("📋 ÉTAPE 2", extra=log_marks.SECTION)
    logging.getLogger("promptodys.app").info("✅ suite")

    records = []
    while not configured.console.empty():
        records.append(configured.console.get_nowait())
    assert [log_marks.is_section(record) for record in records] == [True, False]
    assert "INFO promptodys.app : 📋 ÉTAPE 2\n" in configured.file_text()


def test_error_traceback_in_file_not_in_console(configured):
    try:
        raise ValueError("boum")
    except ValueError:
        logging.getLogger("promptodys.app").error("❌ échec", exc_info=True)

    assert configured.console_messages() == ["❌ échec"]
    file_text = configured.file_text()
    assert "Traceback" in file_text
    assert "ValueError: boum" in file_text


def test_library_logs_go_to_file_from_warning_only(configured):
    library = logging.getLogger("google.genai")
    library.info("info d'une bibliothèque")
    library.warning("avertissement d'une bibliothèque")

    assert configured.console_messages() == []
    file_text = configured.file_text()
    assert "info d'une bibliothèque" not in file_text
    assert "WARNING google.genai : avertissement d'une bibliothèque" in file_text


def test_stderr_lines_become_errors(configured):
    stderr = configured.stderr_stream
    stderr.write("ligne 1\nligne ")
    stderr.write("2\n\n")
    stderr.write("fin sans retour")
    stderr.flush()

    assert configured.console_messages() == ["ligne 1", "ligne 2", "fin sans retour"]
    assert "ERROR promptodys.stderr : ligne 1" in configured.file_text()


def test_uncaught_exception_is_logged(configured):
    try:
        raise ValueError("boum")
    except ValueError as e:
        sys.excepthook(ValueError, e, e.__traceback__)

    assert configured.console_messages() == ["❌ Erreur inattendue : ValueError: boum"]
    assert "Traceback" in configured.file_text()


def test_keyboard_interrupt_is_not_an_error(configured, monkeypatch):
    """Ctrl+C dans le terminal : une ligne INFO, le traceback sur le vrai terminal, aucun ERROR."""
    real_terminal = io.StringIO()
    monkeypatch.setattr(sys, "__stderr__", real_terminal)
    # Comme dans l'application : sys.stderr est le flux de configure(), pas celui de pytest
    monkeypatch.setattr(sys, "stderr", configured.stderr_stream)
    try:
        raise KeyboardInterrupt
    except KeyboardInterrupt as e:
        sys.excepthook(KeyboardInterrupt, e, e.__traceback__)

    assert configured.console_messages() == ["⌨️ Arrêt demandé par Ctrl+C"]
    assert "ERROR" not in configured.file_text()
    assert "Traceback" in real_terminal.getvalue()


def test_uncaught_thread_exception_is_logged(configured):
    def fail():
        raise ValueError("boum")

    thread = threading.Thread(target=fail, name="traitement")
    thread.start()
    thread.join()

    assert configured.console_messages() == ["❌ Erreur inattendue dans le thread traitement : ValueError: boum"]
    assert "Traceback" in configured.file_text()


def test_thread_system_exit_is_not_an_error(configured):
    """Eel termine son thread par sys.exit() à la fermeture de l'éditeur : ce n'est pas une erreur."""
    thread = threading.Thread(target=sys.exit)
    thread.start()
    thread.join()

    assert configured.console_messages() == []


# --- ReportLogCollector ---


def test_collector_keeps_info_and_above_of_its_thread(caplog):
    caplog.set_level(logging.DEBUG, logger="promptodys")
    logger = logging.getLogger("promptodys.app")

    with logs.ReportLogCollector() as collector:
        logger.debug("🔍 détail")
        logger.info("✅ étape")
        logger.warning("⚠️ attention")
        logger.error("❌ échec")

    assert collector.messages == ["✅ étape", "⚠️ attention", "❌ échec"]


def test_collector_ignores_ai_stream(caplog):
    caplog.set_level(logging.INFO, logger="promptodys")

    with logs.ReportLogCollector() as collector:
        logging.getLogger(processing.STREAM_LOGGER_NAME).info("morceau du flux")
        logging.getLogger("promptodys.domain.processing").info("✅ flux reçu")

    assert collector.messages == ["✅ flux reçu"]


def test_collector_ignores_other_threads(caplog):
    caplog.set_level(logging.INFO, logger="promptodys")
    logger = logging.getLogger("promptodys.presentation.panel_controller")

    with logs.ReportLogCollector() as collector:
        other = threading.Thread(target=lambda: logger.info("💾 sauvegarde pendant le traitement"))
        other.start()
        other.join()
        logger.info("✅ étape du traitement")

    assert collector.messages == ["✅ étape du traitement"]


def test_collector_is_removed_on_exit(caplog):
    caplog.set_level(logging.INFO, logger="promptodys")
    logger = logging.getLogger("promptodys.app")

    with logs.ReportLogCollector() as collector:
        logger.info("pendant")
    logger.info("après")

    assert collector.messages == ["pendant"]
    assert collector not in logging.getLogger("promptodys").handlers
