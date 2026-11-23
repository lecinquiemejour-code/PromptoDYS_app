"""Journalisation de PromptoDYS : où va chaque log.

Le code se contente d'appeler _logger.debug/info/warning/error ; c'est configure(), appelée une fois
par main(), qui décide des destinations :

| Niveau             | Console du panneau | Terminal (dev) | Fichier logs/promptodys.log |
|--------------------|--------------------|----------------|-----------------------------|
| DEBUG              | —                  | oui            | oui                         |
| INFO, WARNING      | oui                | oui            | oui                         |
| ERROR              | oui, message seul  | oui            | oui, avec traceback         |
| bibliothèques      | —                  | —              | WARNING et au-delà          |

Le rapport PDF reçoit en plus les logs d'un traitement IA, par un ReportLogCollector accroché
le temps de ce traitement.
"""

import logging
import logging.handlers
import os
import queue
import sys
import threading
import traceback
from types import TracebackType
from typing import Self, TextIO

from promptodys.domain import log_marks, processing

PACKAGE_LOGGER_NAME = "promptodys"
STDERR_LOGGER_NAME = "promptodys.stderr"

LOG_FILE_NAME = "promptodys.log"
LOG_FILE_MAX_BYTES = 1_000_000  # au-delà, le fichier est renommé en .1 et un nouveau commence
LOG_FILE_BACKUP_COUNT = 3

FILE_FORMAT = "%(asctime)s %(levelname)s %(name)s : %(message)s"
TERMINAL_FORMAT = "%(levelname)-7s %(message)s"


class MessageOnlyFormatter(logging.Formatter):
    """Le message seul, sans niveau ni traceback : la console de l'élève n'affiche pas les détails
    techniques, qui restent dans le fichier de log."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


class _StderrToLogger:
    """Remplace sys.stderr : chaque ligne écrite devient un log ERROR (logger promptodys.stderr).
    Récupère ce que les bibliothèques (eel, gevent) écrivent directement sur stderr, invisible
    sinon dans l'exe, qui n'a pas de terminal."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._buffer = ""
        self._lock = threading.Lock()
        self._local = threading.local()

    def write(self, text: str) -> int:
        # Un handler en échec écrit son erreur sur stderr : sans ce garde-fou, on bouclerait
        if getattr(self._local, "busy", False):
            if sys.__stderr__ is not None:
                sys.__stderr__.write(text)
            return len(text)
        with self._lock:
            self._buffer += text
            *lines, self._buffer = self._buffer.split("\n")
        self._log(lines)
        return len(text)

    def flush(self) -> None:
        with self._lock:
            lines, self._buffer = [self._buffer], ""
        self._log(lines)

    def _log(self, lines: list[str]) -> None:
        self._local.busy = True
        try:
            for line in lines:
                if line.strip():
                    self._logger.error(line)
        finally:
            self._local.busy = False


def configure(
    log_dir: str,
    console_queue: queue.Queue[logging.LogRecord],
    terminal: TextIO | None = sys.__stderr__,
) -> None:
    """Branche les destinations des logs. Appelée une fois par main(), avant le premier log.

    log_dir : dossier du fichier de log (créé s'il n'existe pas).
    console_queue : file lue par le panneau, sur le thread de l'interface, pour remplir sa console.
    terminal : flux du terminal, absent (None) dans l'exe fenêtré.
    """
    os.makedirs(log_dir, exist_ok=True)

    # Fichier, sur le logger racine : il reçoit les logs du paquet (qui remontent jusqu'à la racine)
    # et ceux des bibliothèques à partir de WARNING
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, LOG_FILE_NAME),
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    root.addHandler(file_handler)

    # Console et terminal, sur le logger du paquet : les bibliothèques n'y apparaissent pas
    package = logging.getLogger(PACKAGE_LOGGER_NAME)
    package.setLevel(logging.DEBUG)
    package.propagate = True
    console_handler = logging.handlers.QueueHandler(console_queue)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(MessageOnlyFormatter())
    package.addHandler(console_handler)
    if terminal is not None:
        terminal_handler = logging.StreamHandler(terminal)
        terminal_handler.setLevel(logging.DEBUG)
        terminal_handler.setFormatter(logging.Formatter(TERMINAL_FORMAT))
        package.addHandler(terminal_handler)

    # Erreurs imprévues : elles allaient sur stderr, elles passent par les logs
    logging.captureWarnings(True)  # module warnings → logger py.warnings → fichier
    sys.excepthook = _log_uncaught_exception
    threading.excepthook = _log_uncaught_thread_exception
    sys.stderr = _StderrToLogger(logging.getLogger(STDERR_LOGGER_NAME))


def _log_uncaught_exception(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
    """Exception non rattrapée du thread principal"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Ctrl+C dans le terminal (dev) : arrêt voulu, pas une erreur. Le traceback va sur le vrai
        # terminal ; sys.stderr le transformerait en logs ERROR
        logging.getLogger(PACKAGE_LOGGER_NAME).info("⌨️ Arrêt demandé par Ctrl+C")
        if sys.__stderr__ is not None:
            traceback.print_exception(exc_type, exc, tb, file=sys.__stderr__)
        return
    logging.getLogger(PACKAGE_LOGGER_NAME).error(
        f"❌ Erreur inattendue : {exc_type.__name__}: {exc}", exc_info=(exc_type, exc, tb)
    )


def _log_uncaught_thread_exception(args: threading.ExceptHookArgs) -> None:
    """Exception non rattrapée d'un autre thread"""
    # Comme le comportement par défaut : SystemExit termine le thread sans erreur (Eel s'en sert
    # à la fermeture de la fenêtre de l'éditeur)
    if args.exc_type is SystemExit or args.exc_value is None:
        return
    thread_name = args.thread.name if args.thread is not None else "?"
    logging.getLogger(PACKAGE_LOGGER_NAME).error(
        f"❌ Erreur inattendue dans le thread {thread_name} : {args.exc_type.__name__}: {args.exc_value}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


class ReportLogCollector(logging.Handler):
    """Garde les logs d'un traitement IA pour la section « Log Complet du Traitement IA » du rapport PDF.

    S'utilise avec with : accroché au logger du paquet à l'entrée, retiré à la sortie.
    Ne garde que les logs du thread qui l'a créé (celui du traitement), à partir d'INFO,
    sans les morceaux du flux de l'IA, qui ont leur propre section dans le rapport.
    Comme la console, ajoute une ligne vide ("") avant un message marqué log_marks.SECTION.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.messages: list[str] = []
        self._thread = threading.get_ident()

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self._thread or record.name == processing.STREAM_LOGGER_NAME:
            return
        if log_marks.is_section(record) and self.messages:
            self.messages.append("")
        self.messages.append(record.getMessage())

    def __enter__(self) -> Self:
        logging.getLogger(PACKAGE_LOGGER_NAME).addHandler(self)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        logging.getLogger(PACKAGE_LOGGER_NAME).removeHandler(self)
