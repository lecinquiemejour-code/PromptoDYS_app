"""Adaptateurs provisoires de askGeminiPrompto.py : disque réel (dossier temporaire), Eel et Gemini simulés."""

import base64
from types import SimpleNamespace

import eel

import askGeminiPrompto as app
from promptodys.domain import ports

PNG = b"\x89PNG\r\n\x1a\n donnees"


def _document():
    return ports.Document(
        markdown="# Cours\n![schema](./images/schema.png)",
        images=[ports.Image(filename="schema.png", content=PNG, mime_type="image/png")],
    )


# --- DiskDocumentStore ---


def test_disk_store_save_creates_arduino_layout(tmp_path):
    """Le document est rangé dans <dossier>/<nom>/<nom>.md, ses images dans images/."""
    doc_dir = app.DiskDocumentStore().save(_document(), str(tmp_path), "cours")
    assert doc_dir == str(tmp_path / "cours")
    assert (tmp_path / "cours" / "cours.md").read_text(encoding="utf-8") == _document().markdown
    assert (tmp_path / "cours" / "images" / "schema.png").read_bytes() == PNG


def test_disk_store_round_trip_from_md_file_or_folder(tmp_path):
    """Un document enregistré se relit à l'identique, par son fichier .md comme par son dossier."""
    store = app.DiskDocumentStore()
    doc_dir = store.save(_document(), str(tmp_path), "cours")
    assert store.load(str(tmp_path / "cours" / "cours.md")) == (_document(), doc_dir)
    assert store.load(doc_dir) == (_document(), doc_dir)


def test_disk_store_load_ignores_non_images(tmp_path):
    """Un fichier qui n'est pas une image, dans images/, n'est pas chargé."""
    store = app.DiskDocumentStore()
    doc_dir = store.save(_document(), str(tmp_path), "cours")
    (tmp_path / "cours" / "images" / "notes.txt").write_text("pas une image")
    document, _ = store.load(doc_dir)
    assert [image.filename for image in document.images] == ["schema.png"]


def test_disk_store_load_invalid_path(tmp_path):
    """Un chemin qui n'existe pas, ou un dossier sans .md du même nom, ne donne aucun document."""
    store = app.DiskDocumentStore()
    assert store.load(str(tmp_path / "absent")) is None
    (tmp_path / "vide").mkdir()
    assert store.load(str(tmp_path / "vide")) is None


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


# --- GeminiModel ---


def _response(parts, usage=None):
    """Morceau de réponse au format du SDK google-genai (seuls les attributs lus)."""
    content = SimpleNamespace(parts=[SimpleNamespace(text=text, thought=thought) for text, thought in parts])
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)], usage_metadata=usage)


def test_gemini_model_converts_responses_to_chunks():
    """Réflexion et réponse deviennent des AIChunk, les parties vides sont ignorées, les jetons arrivent en dernier."""
    usage = SimpleNamespace(
        prompt_token_count=10, candidates_token_count=20, thoughts_token_count=5, total_token_count=35
    )
    responses = [
        _response([("je réfléchis", True), ("", False)]),
        SimpleNamespace(candidates=[], usage_metadata=None),
        _response([("<NOTE>ok</NOTE>", None)], usage=usage),
    ]
    client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=lambda **kwargs: iter(responses)))

    chunks = list(app.GeminiModel(client).stream("prompt"))

    assert chunks == [
        ports.AIChunk(text="je réfléchis", thought=True),
        ports.AIChunk(text="<NOTE>ok</NOTE>", thought=False),
        ports.AIChunk(usage={"input": 10, "output": 20, "thinking": 5, "total": 35}),
    ]
