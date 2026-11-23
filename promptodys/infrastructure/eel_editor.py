"""Éditeur React affiché dans Chrome et joint par le pont Eel.

- EelEditor : adaptateur du port Editor (lecture et écriture du document) ;
- init(), start(), close() : préparation, ouverture et fermeture de la fenêtre de l'éditeur ;
- EelWindow : start(), close() et wait_for_free_port() réunis pour le panneau de contrôle ;
- on_editor_open(), on_editor_close() : événements envoyés par React, transmis aux fonctions
  enregistrées par set_event_handlers() ;
- is_port_free(), wait_for_free_port() : disponibilité du port du serveur Eel.

Les fonctions exposées à JavaScript restent synchrones (voir ARCHITECTURE.md, « Règle technique importante »).
"""

import base64
import logging
import mimetypes
import socket
import sys
import time
from collections.abc import Callable
from typing import Any

import eel

from promptodys.domain import ports

_logger = logging.getLogger(__name__)

# Les fonctions JavaScript (readMarkdown, writeDocumentData, closeEditor...) sont ajoutées
# dynamiquement au module eel par eel.init() : pyright ne peut pas les connaître.
_js: Any = eel

# --- Événements envoyés par React ---

_on_open: Callable[[], None] | None = None
_on_close: Callable[[], None] | None = None


def set_event_handlers(on_open: Callable[[], None], on_close: Callable[[], None]) -> None:
    """Fonctions appelées quand React signale l'ouverture puis la fermeture de l'éditeur.
    Elles sont appelées depuis un thread d'Eel, jamais depuis celui de l'interface."""
    global _on_open, _on_close
    _on_open, _on_close = on_open, on_close


@eel.expose
def on_editor_open() -> None:
    """Appelé par React quand l'éditeur est monté"""
    _logger.info("✅ Éditeur ouvert (notifié par React)")
    if _on_open is not None:
        _on_open()


@eel.expose
def on_editor_close() -> None:
    """Appelé par React avant la fermeture de la fenêtre"""
    _logger.info("🔴 Éditeur fermé (notifié par React)")
    if _on_close is not None:
        _on_close()


# --- Fenêtre de l'éditeur ---

_WINDOW_SIZE = (1200, 800)


def init(web_folder: str) -> None:
    """Prépare Eel à servir l'éditeur (dossier de index.html), sans ouvrir de fenêtre"""
    eel.init(web_folder)


def start(port: int, chrome_profile_dir: str) -> None:
    """Ouvre l'éditeur dans une fenêtre Chrome et bloque jusqu'à sa fermeture.
    Si Chrome ne démarre pas, essaie un mode de secours ; lève son exception s'il échoue aussi"""
    try:
        eel.start(
            "index.html",
            mode="chrome",
            size=_WINDOW_SIZE,
            port=port,
            cmdline_args=[
                f"--app=http://localhost:{port}/index.html",
                f"--user-data-dir={chrome_profile_dir}",
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
        _logger.warning(f"⚠️ Chrome n'a pas démarré ({e}) : ouverture dans le navigateur par défaut")
        # Mode de secours : Eel 0.18 ne connaît pas « chrome-app » et ouvre le navigateur par défaut
        eel.start(
            "index.html",
            mode="chrome-app",
            size=_WINDOW_SIZE,
            port=port,
            cmdline_args=[
                f"--user-data-dir={chrome_profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            block=True,
        )


def close() -> None:
    """Demande à l'éditeur React de fermer sa fenêtre. Lève une exception si la demande n'a pas pu partir
    (bundle sans closeEditor, connexion déjà fermée)"""
    _js.closeEditor()


# --- Disponibilité du port de l'éditeur ---


def is_port_free(port: int) -> bool:
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


def wait_for_free_port(port: int, timeout: float = 5.0) -> bool:
    """Attend que le port se libère, au plus timeout secondes (serveur Eel précédent pas encore arrêté)"""
    deadline = time.monotonic() + timeout
    while not is_port_free(port):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)
    return True


class EelWindow:
    """Fenêtre de l'éditeur, telle que le panneau de contrôle la manipule
    (EditorWindow de presentation.panel_controller). N'hérite pas du Protocol : l'infrastructure
    n'importe pas presentation, la compatibilité est vérifiée par pyright à l'assemblage (promptodys.app)."""

    def __init__(self, port: int, chrome_profile_dir: str) -> None:
        self.port = port
        self._chrome_profile_dir = chrome_profile_dir

    def wait_for_free_port(self) -> bool:
        """Attend que le port de l'éditeur se libère, faux s'il reste occupé"""
        return wait_for_free_port(self.port)

    def start(self) -> None:
        """Ouvre l'éditeur et bloque jusqu'à sa fermeture ; lève une exception si Chrome ne démarre pas"""
        start(self.port, self._chrome_profile_dir)

    def close(self) -> None:
        """Demande à React de fermer la fenêtre ; lève une exception si la demande n'a pas pu partir"""
        close()


# --- Adaptateur du port Editor ---


def _show_content(content: str, title: str) -> None:
    """Contenu complet de l'éditeur, en DEBUG (fichier de log et terminal) : il est déjà dans le rapport"""
    _logger.debug(f"🔍 {title}\n{'=' * 50}\n{content if content.strip() else '📝 (Éditeur vide)'}\n{'=' * 50}")


class EelEditor(ports.Editor):
    """Éditeur React, joint par le pont Eel.
    Les images voyagent en base64 côté JavaScript, en binaire côté domaine."""

    def read_markdown(self) -> str:
        try:
            content: str = _js.readMarkdown()()
            _logger.info(f"✅ SUCCÈS: Contenu récupéré ({len(content)} caractères)")
        except Exception as e:
            _logger.error(f"❌ ÉCHEC: Erreur lecture: {e}")
            content = ""
        _show_content(content, "📄 CONTENU LU DEPUIS L'ÉDITEUR")
        return content

    def write_markdown(self, markdown: str) -> bool:
        _show_content(markdown, "📄 CONTENU À INJECTER DANS L'ÉDITEUR")
        try:
            _js.writeMarkdown(markdown)
            _logger.info(f"✅ SUCCÈS: Contenu injecté ({len(markdown)} caractères)")
            return True
        except Exception as e:
            _logger.error(f"❌ ÉCHEC: Erreur écriture: {e}")
            return False

    def read_document(self) -> ports.Document | None:
        """Document de l'éditeur (texte + images), None si l'éditeur n'a rien renvoyé"""
        _logger.debug("🔍 Appel eel.readDocumentData()()...")
        try:
            data = _js.readDocumentData()()
            _logger.debug(f"🔍 readDocumentData retour → type={type(data).__name__}")
            if data is None:
                _logger.debug("🔍 readDocumentData → None (la fonction JS retourne undefined ou null)")
            elif isinstance(data, dict):
                _logger.debug(f"🔍 readDocumentData → dict avec clés: {list(data.keys())}")
                if "markdown" in data:
                    _logger.debug(f"🔍   markdown: {len(data['markdown'])} caractères")
                if "images" in data:
                    _logger.debug(f"🔍   images: {len(data['images'])} image(s)")
            elif isinstance(data, str):
                _logger.debug(f"🔍 readDocumentData → string ({len(data)} car.): {repr(data)[:200]}")
            elif isinstance(data, bool):
                _logger.debug(f"🔍 readDocumentData → bool: {data}")
            else:
                _logger.debug(f"🔍 readDocumentData → {type(data).__name__}: {repr(data)[:500]}")
        except Exception as e:
            _logger.error(f"❌ SAUVEGARDE: Erreur appel readDocumentData: {type(e).__name__}: {e}", exc_info=True)
            return None

        if not data or not isinstance(data, dict):
            _logger.error(f"❌ SAUVEGARDE: Aucune donnée exploitable reçue de l'éditeur ({repr(data)[:200]})")
            return None

        _logger.info(f"📄 SAUVEGARDE: Markdown reçu ({len(data.get('markdown', ''))} caractères)")
        _logger.info(f"🖼️ SAUVEGARDE: {len(data.get('images', []))} image(s) reçue(s)")

        images: list[ports.Image] = []
        for image in data.get("images", []):
            try:
                mime_type = image.get("mimeType") or mimetypes.guess_type(image["filename"])[0] or ""
                images.append(
                    ports.Image(
                        filename=image["filename"], content=base64.b64decode(image["data"]), mime_type=mime_type
                    )
                )
            except Exception as e:
                _logger.error(f"  ❌ Erreur image '{image.get('filename')}': {e}")
        return ports.Document(markdown=data.get("markdown", ""), images=images)

    def write_document(self, document: ports.Document) -> bool:
        """Charge le document dans l'éditeur. Faux si l'appel Eel a échoué"""
        images_to_send: list[dict[str, str]] = [
            {
                "filename": image.filename,
                "data": base64.b64encode(image.content).decode("utf-8"),
                "mimeType": image.mime_type,
            }
            for image in document.images
        ]
        data_to_send = {"markdown": document.markdown, "images": images_to_send}
        nb_car, nb_images = len(document.markdown), len(images_to_send)
        _logger.info(f"📤 OUVERTURE: Envoi à l'éditeur ({nb_car} car. + {nb_images} image(s))...")
        _logger.debug(f"🔍 Appel eel.writeDocumentData() avec {nb_car} car. + {nb_images} image(s)...")
        _logger.debug(f"🔍 data_to_send → clés={list(data_to_send.keys())}")
        _logger.debug(f"🔍   markdown: {nb_car} car., début: {repr(document.markdown[:100])}")
        _logger.debug(f"🔍   images: {nb_images} élément(s)")
        for i, img in enumerate(images_to_send):
            _logger.debug(
                f"🔍   image[{i}]: filename={img['filename']}, mimeType={img['mimeType']}, "
                f"data={len(img['data'])} car. base64"
            )

        try:
            result = _js.writeDocumentData(data_to_send)()
            _logger.debug(f"🔍 writeDocumentData retour → type={type(result).__name__}, valeur={repr(result)}")
            if result is None:
                _logger.info(
                    "✅ OUVERTURE TERMINÉE: document chargé (retour: None/undefined — normal si JS ne retourne rien)"
                )
            elif result:
                _logger.info("✅ OUVERTURE TERMINÉE: document chargé dans l'éditeur")
            else:
                _logger.warning(
                    f"⚠️ OUVERTURE: writeDocumentData a retourné {repr(result)} "
                    "(le document peut quand même être chargé)"
                )
            return True
        except Exception as e:
            _logger.error(f"❌ OUVERTURE: Erreur appel writeDocumentData: {type(e).__name__}: {e}", exc_info=True)
            return False
