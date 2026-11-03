"""Assemblage du traitement IA dans askGeminiPrompto.py, avec Gemini, l'éditeur et le PDF simulés."""

import threading

import pytest

import askGeminiPrompto as app
from promptodys.domain import ports


class _Editor:
    def __init__(self):
        self.writes = []

    def read_markdown(self):
        return "Note brute"

    def write_markdown(self, markdown):
        self.writes.append(markdown)
        return True


class _Model:
    def __init__(self, client):
        pass

    def stream(self, prompt):
        yield ports.AIChunk(text="<NOTE>Note corrigée</NOTE>")


@pytest.fixture
def traitement(monkeypatch):
    """Remplace Gemini, l'éditeur et le PDF ; renvoie (éditeur, rapports demandés)."""
    editor = _Editor()
    rapports = []
    monkeypatch.setattr(app, "init_gemini_client", lambda: object())
    monkeypatch.setattr(app, "GeminiModel", _Model)
    monkeypatch.setattr(app, "lire_prompto_dys", lambda: "Corrige : [TEXTE]")
    monkeypatch.setattr(app, "editeur_eel", editor)
    monkeypatch.setattr(app, "sauvegarder_rapport", lambda **kwargs: rapports.append(kwargs) or (None, "r.pdf"))
    monkeypatch.setattr(app, "logs_complets", [])
    return editor, rapports


def test_traitement_gemini_completed(traitement):
    """Le traitement abouti injecte la note et produit le rapport avec les logs des étapes 1 à 4."""
    editor, rapports = traitement

    assert app.traitement_gemini(threading.Event())

    assert editor.writes[0].startswith("Note corrigée")
    [rapport] = rapports
    assert rapport["contenu_original"] == "Note brute"
    assert rapport["contenu_traite"] == editor.writes[0]
    logs = "\n".join(rapport["logs_etapes"])
    for etape in ("ÉTAPE 1", "ÉTAPE 2", "ÉTAPE 3", "ÉTAPE 4"):
        assert etape in logs
    assert "ÉTAPE 5" not in logs


def test_traitement_gemini_cancelled_produces_no_report(traitement):
    """Un traitement abandonné renvoie faux, sans rien écrire ni produire de rapport."""
    editor, rapports = traitement
    annulation = threading.Event()
    annulation.set()

    assert not app.traitement_gemini(annulation)

    assert editor.writes == []
    assert rapports == []


def test_traitement_gemini_without_client(traitement, monkeypatch):
    """Sans client Gemini (clé absente), le traitement échoue avant de lire l'éditeur."""
    editor, rapports = traitement
    monkeypatch.setattr(app, "init_gemini_client", lambda: None)

    assert not app.traitement_gemini(threading.Event())

    assert editor.writes == []
    assert rapports == []
