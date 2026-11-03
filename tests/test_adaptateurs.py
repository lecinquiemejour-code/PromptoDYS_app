"""Adaptateurs provisoires de askGeminiPrompto.py : disque réel (dossier temporaire), Eel et Gemini simulés."""

import base64

import eel

import askGeminiPrompto as app
from promptodys.domain import ports

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
    document = app.EelEditor().read_document()
    assert document == ports.Document(
        markdown="# Cours", images=[ports.Image(filename="schema.png", content=PNG, mime_type="image/png")]
    )


def test_eel_editor_read_document_without_data(monkeypatch):
    """Si l'éditeur ne renvoie rien, il n'y a pas de document."""
    monkeypatch.setattr(eel, "readDocumentData", lambda: lambda: None, raising=False)
    assert app.EelEditor().read_document() is None


def test_eel_editor_write_document_encodes_base64(monkeypatch):
    """Les images sont envoyées à l'éditeur en base64, avec leur type MIME."""
    sent = []
    monkeypatch.setattr(eel, "writeDocumentData", lambda data: sent.append(data) or (lambda: True), raising=False)
    assert app.EelEditor().write_document(_document())
    assert sent == [
        {
            "markdown": _document().markdown,
            "images": [{"filename": "schema.png", "data": base64.b64encode(PNG).decode(), "mimeType": "image/png"}],
        }
    ]
