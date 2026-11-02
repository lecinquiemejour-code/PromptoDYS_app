"""Faux adaptateurs des ports du domaine, écrits à la main : ni Eel, ni Gemini, ni disque."""

import pytest

from promptodys.domain import ports


class FakeEditor:
    """Éditeur en mémoire. writes garde chaque texte injecté, loaded chaque document chargé."""

    def __init__(self, markdown="", document=None, accepts_writes=True):
        self.markdown = markdown
        self.document = document
        self.accepts_writes = accepts_writes
        self.writes = []
        self.loaded = []

    def read_markdown(self):
        return self.markdown

    def write_markdown(self, markdown):
        self.writes.append(markdown)
        return self.accepts_writes

    def read_document(self):
        return self.document

    def write_document(self, document):
        self.loaded.append(document)
        return self.accepts_writes


class FakeModel:
    """IA qui renvoie des morceaux prévus à l'avance, puis lève error si elle est fournie.
    on_chunk(index) est appelé avant chaque morceau, par exemple pour simuler un abandon."""

    def __init__(self, chunks, error=None, on_chunk=None):
        self.chunks = chunks
        self.error = error
        self.on_chunk = on_chunk
        self.prompts = []

    def stream(self, prompt):
        self.prompts.append(prompt)
        for index, chunk in enumerate(self.chunks):
            if self.on_chunk:
                self.on_chunk(index)
            yield chunk
        if self.error:
            raise self.error


class FakeStore:
    """Rangement en mémoire : saved garde (document, dossier, nom) de chaque enregistrement."""

    def __init__(self, loaded=None, save_result="/docs/note"):
        self.loaded = loaded
        self.save_result = save_result
        self.saved = []

    def save(self, document, directory, name):
        self.saved.append((document, directory, name))
        return self.save_result

    def load(self, path):
        return self.loaded


@pytest.fixture
def document():
    return ports.Document(
        markdown="# Cours\n![schema](./images/schema.png)",
        images=[ports.Image(filename="schema.png", content=b"\x89PNG", mime_type="image/png")],
    )


@pytest.fixture
def fake_editor():
    return FakeEditor


@pytest.fixture
def fake_model():
    return FakeModel


@pytest.fixture
def fake_store():
    return FakeStore
