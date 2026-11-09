"""Pont Eel vers l'éditeur React : adaptateur EelEditor (Eel simulé), événements de React, port du serveur."""

import base64
import socket

import eel
import pytest

from promptodys.domain import ports
from promptodys.infrastructure import eel_editor
from promptodys.infrastructure.eel_editor import EelEditor

PNG = b"\x89PNG\r\n\x1a\n donnees"


def _document():
    return ports.Document(
        markdown="# Cours\n![schema](./images/schema.png)",
        images=[ports.Image(filename="schema.png", content=PNG, mime_type="image/png")],
    )


# --- EelEditor ---


def test_eel_editor_read_document_decodes_base64(monkeypatch):
    """Les images reçues en base64 de l'éditeur deviennent du binaire."""
    data = {
        "markdown": "# Cours",
        "images": [{"filename": "schema.png", "data": base64.b64encode(PNG).decode()}],
    }
    monkeypatch.setattr(eel, "readDocumentData", lambda: lambda: data, raising=False)
    document = EelEditor().read_document()
    assert document == ports.Document(
        markdown="# Cours", images=[ports.Image(filename="schema.png", content=PNG, mime_type="image/png")]
    )


def test_eel_editor_read_document_without_data(monkeypatch):
    """Si l'éditeur ne renvoie rien, il n'y a pas de document."""
    monkeypatch.setattr(eel, "readDocumentData", lambda: lambda: None, raising=False)
    assert EelEditor().read_document() is None


def test_eel_editor_write_document_encodes_base64(monkeypatch):
    """Les images sont envoyées à l'éditeur en base64, avec leur type MIME."""
    sent = []
    monkeypatch.setattr(eel, "writeDocumentData", lambda data: sent.append(data) or (lambda: True), raising=False)
    assert EelEditor().write_document(_document())
    assert sent == [
        {
            "markdown": _document().markdown,
            "images": [{"filename": "schema.png", "data": base64.b64encode(PNG).decode(), "mimeType": "image/png"}],
        }
    ]


# --- Événements envoyés par React ---


@pytest.fixture
def handlers(monkeypatch):
    """Enregistre deux fonctions qui notent les événements reçus ; état d'origine rétabli après le test."""
    monkeypatch.setattr(eel_editor, "_on_open", None)
    monkeypatch.setattr(eel_editor, "_on_close", None)
    events = []
    eel_editor.set_event_handlers(lambda: events.append("open"), lambda: events.append("close"))
    return events


def test_react_events_reach_registered_handlers(handlers):
    """L'ouverture puis la fermeture signalées par React appellent les fonctions enregistrées."""
    eel_editor.on_editor_open()
    eel_editor.on_editor_close()
    assert handlers == ["open", "close"]


def test_react_events_without_handlers(monkeypatch):
    """Sans fonctions enregistrées, un signal de React ne lève pas d'exception."""
    monkeypatch.setattr(eel_editor, "_on_open", None)
    monkeypatch.setattr(eel_editor, "_on_close", None)
    eel_editor.on_editor_open()
    eel_editor.on_editor_close()


def test_react_events_are_exposed_under_the_names_used_by_javascript():
    """useEelBridge.js appelle window.eel.on_editor_open et on_editor_close : ces noms ne doivent pas changer."""
    exposed = eel._exposed_functions
    assert exposed["on_editor_open"] is eel_editor.on_editor_open
    assert exposed["on_editor_close"] is eel_editor.on_editor_close


def test_close_asks_react_to_close_the_window(monkeypatch):
    """close() appelle la fonction JavaScript closeEditor."""
    calls = []
    monkeypatch.setattr(eel, "closeEditor", lambda: calls.append("closeEditor"), raising=False)
    eel_editor.close()
    assert calls == ["closeEditor"]


# --- Port du serveur Eel ---


def _port_inutilise():
    """Un port que personne n'écoute (réservé puis relâché aussitôt)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("localhost", 0))
        return sock.getsockname()[1]


def test_port_is_free_when_nobody_listens():
    """Un port inutilisé est vu comme libre."""
    assert eel_editor.is_port_free(_port_inutilise())


def test_port_is_busy_when_a_program_listens():
    """Un port sur lequel un programme écoute est vu comme occupé (constat B5)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
        serveur.bind(("localhost", 0))
        serveur.listen()
        assert not eel_editor.is_port_free(serveur.getsockname()[1])


def test_wait_for_free_port_gives_up_after_timeout():
    """Si le port reste occupé, l'attente s'arrête et renvoie faux."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
        serveur.bind(("localhost", 0))
        serveur.listen()
        assert not eel_editor.wait_for_free_port(serveur.getsockname()[1], timeout=1.0)


# --- EelWindow ---


def test_eel_window_delegates_to_module_functions(monkeypatch):
    """EelWindow transmet son port et son profil Chrome aux fonctions du module."""
    calls = []
    monkeypatch.setattr(eel_editor, "wait_for_free_port", lambda port: calls.append(("wait", port)) or True)
    monkeypatch.setattr(eel_editor, "start", lambda port, profile: calls.append(("start", port, profile)))
    monkeypatch.setattr(eel_editor, "close", lambda: calls.append(("close",)))
    window = eel_editor.EelWindow(8123, "/profil")

    assert window.port == 8123
    assert window.wait_for_free_port()
    window.start()
    window.close()

    assert calls == [("wait", 8123), ("start", 8123, "/profil"), ("close",)]
