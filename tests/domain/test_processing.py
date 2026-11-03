import threading
from datetime import date

from promptodys.domain.ports import AIModelError, AIChunk
from promptodys.domain.processing import ProcessingStatus, process_note

TEMPLATE = "Le [DATE], corrige :\n[TEXTE]"
TODAY = date(2026, 11, 2)
ANSWER = [
    AIChunk(text="je réfléchis", thought=True),
    AIChunk(text="<NOTE>Note "),
    AIChunk(text="corrigée</NOTE>\nDébrief : 1 faute"),
    AIChunk(usage={"input": 10, "output": 20, "thinking": 5, "total": 35}),
]


def _process(editor, model, cancel=None):
    return process_note(editor, model, TEMPLATE, cancel or threading.Event(), TODAY)


def test_process_note_completed(fake_editor, fake_model):
    """La note corrigée, suivie de la note d'origine, est injectée ; le résultat porte tout le reste."""
    editor = fake_editor(markdown="Note brute")
    model = fake_model(ANSWER)

    result = _process(editor, model)

    assert result.status is ProcessingStatus.COMPLETED
    assert model.prompts == ["Le 02/11/2026, corrige :\nNote brute"]
    assert len(editor.writes) == 1
    assert editor.writes[0].startswith("Note corrigée\n\n---\n\n")
    assert editor.writes[0].endswith("Note brute\n")
    assert result.processed_note == editor.writes[0]
    assert result.original_note == "Note brute"
    assert result.correction_debrief == "Débrief : 1 faute"
    assert result.ai_stream == "💭 je réfléchis\n<NOTE>Note corrigée</NOTE>\nDébrief : 1 faute"
    assert result.token_stats == {"input": 10, "output": 20, "thinking": 5, "total": 35}


def test_process_note_step_logs_cover_preparation_only(fake_editor, fake_model):
    """Les logs gardés pour le rapport sont ceux de la préparation, pas le flux de l'IA."""
    result = _process(fake_editor(markdown="Note"), fake_model(ANSWER))
    assert any("ÉTAPE 3" in log for log in result.step_logs)
    assert any("ÉTAPE 4" in log for log in result.step_logs)
    assert not any("Note corrigée" in log for log in result.step_logs)


def test_process_note_without_note_tags_uses_whole_answer(fake_editor, fake_model):
    """Sans balises <NOTE>, toute la réponse devient la note, sans débrief."""
    editor = fake_editor(markdown="Brut")
    result = _process(editor, fake_model([AIChunk(text="Réponse libre")]))
    assert result.status is ProcessingStatus.COMPLETED
    assert editor.writes[0].startswith("Réponse libre\n")
    assert result.correction_debrief == ""


def test_process_note_without_token_stats(fake_editor, fake_model, caplog):
    """Sans statistiques de jetons, le traitement aboutit et le signale."""
    result = _process(fake_editor(markdown="Brut"), fake_model(ANSWER[:3]))
    assert result.status is ProcessingStatus.COMPLETED
    assert result.token_stats == {}
    assert "⚠️ Statistiques non disponibles pour cette réponse" in caplog.messages


def test_process_note_injection_failure_still_completes(fake_editor, fake_model):
    """Un échec d'injection est signalé sans faire échouer le traitement (le rapport reste produit)."""
    result = _process(fake_editor(markdown="Brut", accepts_writes=False), fake_model(ANSWER))
    assert result.status is ProcessingStatus.COMPLETED


def test_process_note_cancelled_during_stream(fake_editor, fake_model):
    """Un abandon pendant le flux arrête tout : rien n'est écrit dans l'éditeur."""
    cancel = threading.Event()
    editor = fake_editor(markdown="Brut")
    model = fake_model(ANSWER, on_chunk=lambda index: index == 2 and cancel.set())

    result = _process(editor, model, cancel)

    assert result.status is ProcessingStatus.CANCELLED
    assert editor.writes == []


def test_process_note_ai_error_fails_without_writing(fake_editor, fake_model, caplog):
    """Une erreur de l'IA fait échouer le traitement, avec son message, sans rien écrire."""
    editor = fake_editor(markdown="Brut")
    result = _process(editor, fake_model(ANSWER[:2], error=AIModelError("Erreur API Gemini: quota")))
    assert result.status is ProcessingStatus.FAILED
    assert editor.writes == []
    assert "\n❌ ÉCHEC: Erreur API Gemini: quota" in caplog.messages


def test_process_note_unexpected_error_fails(fake_editor, fake_model):
    """Une erreur inattendue pendant le flux fait aussi échouer le traitement."""
    editor = fake_editor(markdown="Brut")
    result = _process(editor, fake_model([], error=RuntimeError("connexion perdue")))
    assert result.status is ProcessingStatus.FAILED
    assert editor.writes == []


def test_process_note_error_after_cancel_is_a_cancellation(fake_editor, fake_model, caplog):
    """Après un abandon, une erreur (connexion coupée) n'est pas un échec à signaler."""
    cancel = threading.Event()
    cancel.set()
    result = _process(fake_editor(markdown="Brut"), fake_model([], error=AIModelError("coupé")), cancel)
    assert result.status is ProcessingStatus.CANCELLED
    assert not any("ÉCHEC" in message for message in caplog.messages)
