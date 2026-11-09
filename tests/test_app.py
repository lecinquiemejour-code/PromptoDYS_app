"""Traitement IA assemblé dans promptodys.app (run_processing), avec Gemini, l'éditeur et le PDF simulés."""

import threading

import pytest

from promptodys import app
from promptodys.domain import ports
from promptodys.infrastructure import config, gemini_model, pdf_report


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
    """Remplace Gemini et le PDF ; renvoie (éditeur simulé, rapports demandés)."""
    rapports = []
    monkeypatch.setattr(gemini_model, "create_client", lambda: object())
    monkeypatch.setattr(gemini_model, "GeminiModel", _Model)
    monkeypatch.setattr(config, "read_prompt_template", lambda: "Corrige : [TEXTE]")
    monkeypatch.setattr(pdf_report, "save_report", lambda **kwargs: rapports.append(kwargs) or "r.pdf")
    monkeypatch.setattr(app, "report_logs", [])
    return _Editor(), rapports


def test_run_processing_completed(traitement):
    """Le traitement abouti injecte la note et produit le rapport avec les logs des étapes 1 à 4."""
    editor, rapports = traitement

    assert app.run_processing(editor, threading.Event())

    assert editor.writes[0].startswith("Note corrigée")
    [rapport] = rapports
    assert rapport["original_note"] == "Note brute"
    assert rapport["processed_note"] == editor.writes[0]
    logs = "\n".join(rapport["step_logs"])
    for etape in ("ÉTAPE 1", "ÉTAPE 2", "ÉTAPE 3", "ÉTAPE 4"):
        assert etape in logs
    assert "ÉTAPE 5" not in logs


def test_run_processing_cancelled_produces_no_report(traitement):
    """Un traitement abandonné renvoie faux, sans rien écrire ni produire de rapport."""
    editor, rapports = traitement
    annulation = threading.Event()
    annulation.set()

    assert not app.run_processing(editor, annulation)

    assert editor.writes == []
    assert rapports == []


def test_run_processing_without_client(traitement, monkeypatch):
    """Sans client Gemini (clé absente), le traitement échoue avant de lire l'éditeur."""
    editor, rapports = traitement
    monkeypatch.setattr(gemini_model, "create_client", lambda: None)

    assert not app.run_processing(editor, threading.Event())

    assert editor.writes == []
    assert rapports == []


def test_run_processing_clears_previous_report_logs(traitement):
    """Les logs d'un traitement précédent n'entrent pas dans le rapport du suivant."""
    editor, rapports = traitement
    app.report_logs.append("log d'un traitement précédent")

    assert app.run_processing(editor, threading.Event())

    [rapport] = rapports
    assert "log d'un traitement précédent" not in rapport["step_logs"]
