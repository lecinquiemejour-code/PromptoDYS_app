"""Traitement IA assemblé dans promptodys.app (run_processing), avec Gemini, l'éditeur et le PDF simulés."""

import logging
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
    # Réponse de l'IA, remplaçable par un test
    chunks = [ports.AIChunk(text="<NOTE>Note corrigée</NOTE>")]

    def __init__(self, client):
        pass

    def stream(self, prompt):
        yield from self.chunks


@pytest.fixture
def traitement(monkeypatch, caplog):
    """Remplace Gemini et le PDF ; renvoie (éditeur simulé, rapports demandés)."""
    # Sans main(), logs.configure() n'a pas réglé le niveau : le collecteur du rapport ne recevrait rien
    caplog.set_level(logging.INFO, logger="promptodys")
    rapports = []
    monkeypatch.setattr(gemini_model, "create_client", lambda: object())
    monkeypatch.setattr(gemini_model, "GeminiModel", _Model)
    monkeypatch.setattr(config, "read_prompt_template", lambda: "Corrige : [TEXTE]")
    monkeypatch.setattr(pdf_report, "save_report", lambda **kwargs: rapports.append(kwargs) or "r.pdf")
    return _Editor(), rapports


def test_run_processing_completed(traitement):
    """Le traitement abouti injecte la note et produit le rapport avec les logs des étapes 1 à 9, sans le flux."""
    editor, rapports = traitement

    assert app.run_processing(editor, threading.Event())

    assert editor.writes[0].startswith("Note corrigée")
    [rapport] = rapports
    assert rapport["original_note"] == "Note brute"
    assert rapport["processed_note"] == editor.writes[0]
    logs = "\n".join(rapport["step_logs"])
    for etape in range(1, 10):
        assert f"ÉTAPE {etape}:" in logs
    assert "<NOTE>Note corrigée</NOTE>" not in logs


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


def test_run_processing_report_has_only_its_own_logs(traitement):
    """Deux traitements successifs : le rapport du second ne contient pas les logs du premier."""
    editor, rapports = traitement

    assert app.run_processing(editor, threading.Event())
    assert app.run_processing(editor, threading.Event())

    premier, second = rapports
    assert premier["step_logs"] == second["step_logs"]
    assert sum("ÉTAPE 1:" in log for log in second["step_logs"]) == 1


def test_run_processing_report_has_warnings(traitement, monkeypatch):
    """Un avertissement émis pendant le traitement (balises <NOTE> absentes) entre dans le rapport."""
    editor, rapports = traitement
    monkeypatch.setattr(_Model, "chunks", [ports.AIChunk(text="Réponse sans balises")])

    assert app.run_processing(editor, threading.Event())

    [rapport] = rapports
    assert any("Balises <NOTE> absentes" in log for log in rapport["step_logs"])


def test_run_processing_report_ignores_other_threads(traitement, monkeypatch):
    """Un log d'un autre thread pendant le traitement (une sauvegarde par exemple) n'entre pas dans le rapport."""
    editor, rapports = traitement

    def stream(self, prompt):
        other = threading.Thread(target=lambda: logging.getLogger("promptodys.presentation").info("💾 sauvegarde"))
        other.start()
        other.join()
        yield ports.AIChunk(text="<NOTE>Note corrigée</NOTE>")

    monkeypatch.setattr(_Model, "stream", stream)

    assert app.run_processing(editor, threading.Event())

    [rapport] = rapports
    assert "💾 sauvegarde" not in rapport["step_logs"]
