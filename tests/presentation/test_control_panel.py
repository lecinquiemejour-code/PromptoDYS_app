"""Panneau de contrôle Tkinter, avec un éditeur, un rangement, une fenêtre et un traitement simulés.

Les fenêtres restent cachées (run() n'est jamais appelé). Les threads du panneau passent par root.after,
que Tkinter refuse hors de la boucle principale : _run_loop() la fait tourner le temps nécessaire.
Aucun test n'est sauté : la CI (Windows) et les postes de développement savent créer une fenêtre Tk,
et une TclError est une vraie erreur.

_quit() n'est jamais exécuté : il détruirait la fenêtre en pleine boucle et terminerait le processus
(os._exit). Les tests le remplacent sur le panneau, sans toucher à os._exit, dont pytest-timeout
a besoin pour arrêter un test bloqué sous Windows.
"""

import os
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox

import pytest

import promptodys.presentation.control_panel as panel_module
from promptodys.domain import ports
from promptodys.presentation.control_panel import ControlPanel

ICON = str(Path(__file__).parents[2] / "assets" / "prompto.png")
READY = "🤖 Traiter la prise de note"


class _Editor:
    """Éditeur simulé : enregistre les documents qu'on lui envoie."""

    def __init__(self):
        self.written = []

    def write_document(self, document):
        self.written.append(document)
        return True


class _Store:
    """Rangement simulé : tout chemin désigne le même document, rangé dans le dossier du chemin."""

    document = ports.Document(markdown="# Ma note")

    def load(self, path):
        return self.document, os.path.dirname(path)


class _Window:
    """Fenêtre de l'éditeur simulée : start() bloque jusqu'à release(), comme Chrome jusqu'à sa fermeture."""

    port = 8080

    def __init__(self):
        self.port_free = True
        self.starts = 0
        self.closes = 0
        self.started = threading.Event()
        self._released = threading.Event()

    def wait_for_free_port(self):
        return self.port_free

    def start(self):
        self.starts += 1
        self.started.set()
        self._released.wait(timeout=5)

    def close(self):
        self.closes += 1

    def release(self):
        """Fait se terminer start(), comme à la fermeture de la fenêtre Chrome"""
        self._released.set()


class _Processing:
    """Traitement simulé : bloque jusqu'à finish() ou jusqu'à l'abandon, puis renvoie le résultat choisi."""

    def __init__(self):
        self.calls = 0
        self.started = threading.Event()
        self.done = threading.Event()
        self._finish = threading.Event()
        self.result = True

    def __call__(self, cancel):
        self.calls += 1
        self.started.set()
        while not (self._finish.is_set() or cancel.is_set()):
            time.sleep(0.01)
        self.done.set()
        return self.result and not cancel.is_set()

    def finish(self):
        self._finish.set()


@pytest.fixture
def panel(tmp_path):
    """Panneau construit (fenêtre cachée) ; renvoie (panneau, fenêtre de l'éditeur, traitement).
    L'éditeur et le rangement simulés sont joignables par control_panel._editor et control_panel._store."""
    window, processing = _Window(), _Processing()
    control_panel = ControlPanel(
        editor=_Editor(),
        store=_Store(),
        editor_window=window,
        process_note=processing,
        documents_dir=str(tmp_path),
        reports_dir=str(tmp_path / "reports"),
        icon_path=ICON,
    )
    yield control_panel, window, processing
    window.release()  # Ne pas laisser un thread bloqué dans start()
    processing.finish()
    control_panel._root.destroy()


def _run_loop(panel, condition, timeout=3.0):
    """Fait tourner la boucle Tk jusqu'à ce que condition() soit vraie (au plus timeout secondes)"""
    deadline = time.monotonic() + timeout

    def check():
        if condition() or time.monotonic() > deadline:
            panel._root.quit()
        else:
            panel._root.after(20, check)

    panel._root.after(0, check)
    panel._root.mainloop()
    assert condition()


def _run_loop_for(panel, seconds):
    """Fait tourner la boucle Tk pendant une durée fixe (laisse passer les root.after venant des threads)"""
    panel._root.after(int(seconds * 1000), panel._root.quit)
    panel._root.mainloop()


def _status(panel):
    return panel._status_label.cget("text")


# --- Événements de React ---


def test_react_events_update_state_and_status(panel):
    """on_editor_open et on_editor_close mettent à jour l'état de l'éditeur et la barre de statut."""
    control_panel, _, _ = panel

    control_panel.on_editor_open()
    control_panel._root.update()
    assert control_panel._editor_state.is_open
    assert _status(control_panel) == "✅ Éditeur ouvert"

    control_panel.on_editor_close()
    control_panel._root.update()
    assert not control_panel._editor_state.is_open
    assert _status(control_panel) == "🔴 Éditeur fermé"


# --- Ouverture de l'éditeur ---


def test_second_click_on_open_editor_launches_nothing(panel):
    """Pendant le lancement puis une fois l'éditeur ouvert, un nouveau clic ne relance pas l'éditeur."""
    control_panel, window, _ = panel

    control_panel._open_editor()
    _run_loop(control_panel, window.started.is_set)
    control_panel._open_editor()
    assert _status(control_panel) == "⏳ Ouverture de l'éditeur en cours, veuillez patienter"

    control_panel.on_editor_open()
    control_panel._open_editor()
    assert _status(control_panel) == "✅ L'éditeur est déjà ouvert"
    assert window.starts == 1

    # Fermeture de Chrome : start() retourne, l'éditeur est vu fermé
    window.release()
    _run_loop(
        control_panel,
        lambda: (
            _status(control_panel) == "🔴 Éditeur fermé"
            and not control_panel._editor_state.is_open
            and not control_panel._editor_state.is_starting
        ),
    )


def test_busy_port_opens_no_editor(panel, monkeypatch):
    """Si le port reste occupé, l'éditeur n'est pas lancé et l'élève est prévenu."""
    control_panel, window, _ = panel
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda title, message: errors.append(message))
    window.port_free = False

    control_panel._open_editor()
    _run_loop(control_panel, lambda: errors != [])

    assert window.starts == 0
    assert _status(control_panel) == "❌ Port 8080 déjà utilisé par un autre programme"
    assert not control_panel._editor_state.is_starting


# --- Ouverture d'un document ---


def test_open_document_launches_editor_then_loads_it(panel, tmp_path, monkeypatch):
    """Éditeur fermé : « Ouvrir » lance l'éditeur, attend le signal de React, puis charge le document."""
    control_panel, window, _ = panel
    document_dir = tmp_path / "MonDoc"
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: str(document_dir / "MonDoc.md"))
    monkeypatch.setattr(panel_module, "REACT_SETTLE_DELAY_S", 0)

    control_panel._open_document()
    _run_loop(control_panel, window.started.is_set)
    assert control_panel._editor.written == []  # Rien n'est envoyé avant le signal de React

    control_panel.on_editor_open()
    _run_loop(control_panel, lambda: _status(control_panel) == "✅ 'MonDoc' ouvert !")
    assert control_panel._editor.written == [_Store.document]
    assert control_panel._editor_state.document_path == str(document_dir)
    assert window.starts == 1

    # Fermeture de Chrome dans le test : le thread de lancement ne doit pas survivre à la fenêtre Tk
    window.release()
    _run_loop(control_panel, lambda: not control_panel._editor_state.is_open)


def test_open_document_after_chrome_crash_waits_for_react(panel, tmp_path, monkeypatch):
    """Chrome fermé sans signal de React (plantage) : « Ouvrir » attend de nouveau le signal de React,
    et sans lui n'envoie rien à l'éditeur."""
    control_panel, window, _ = panel
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: str(tmp_path / "MonDoc" / "MonDoc.md"))
    monkeypatch.setattr(panel_module, "REACT_SETTLE_DELAY_S", 0)
    monkeypatch.setattr(panel_module, "EDITOR_READY_TIMEOUT_S", 0.2)

    # Premier éditeur : ouvert, puis Chrome se ferme sans on_editor_close
    control_panel._open_editor()
    _run_loop(control_panel, window.started.is_set)
    control_panel.on_editor_open()
    window.release()
    _run_loop(control_panel, lambda: not control_panel._editor_state.is_open)

    # Le nouvel éditeur ne signale jamais son ouverture
    control_panel._open_document()
    _run_loop(
        control_panel,
        lambda: (
            _status(control_panel) == "❌ Éditeur non prêt (timeout)" and not control_panel._editor_state.is_starting
        ),
    )
    assert control_panel._editor.written == []
    assert window.starts == 2


# --- Traitement IA ---


def test_processing_requires_an_open_editor(panel, monkeypatch):
    """Sans éditeur ouvert, le traitement n'est pas lancé et l'élève est prévenu."""
    control_panel, _, processing = panel
    warnings = []
    monkeypatch.setattr(messagebox, "showwarning", lambda title, message, **kwargs: warnings.append(message))

    control_panel._toggle_processing()

    assert len(warnings) == 1
    assert processing.calls == 0
    assert _status(control_panel) == "⚠️ Éditeur non ouvert"


def test_completed_processing_resets_the_button(panel):
    """Un traitement abouti vide la console au lancement, puis remet le bouton à l'état Prêt."""
    control_panel, _, processing = panel
    control_panel.on_editor_open()
    control_panel._append_to_console("log du traitement précédent")
    control_panel._root.update()

    control_panel._toggle_processing()
    assert control_panel._btn_ai.cget("text") == "⛔ Abandonner le traitement"
    _run_loop(control_panel, processing.started.is_set)
    assert "log du traitement précédent" not in control_panel._console.get("1.0", "end")

    processing.finish()
    _run_loop(control_panel, lambda: _status(control_panel) == "✅ Traitement IA terminé !")
    assert control_panel._btn_ai.cget("text") == READY
    assert control_panel._cancel_event is None


def test_failed_processing_shows_failure(panel):
    """Un traitement en échec remet le bouton à l'état Prêt et renvoie aux logs."""
    control_panel, _, processing = panel
    control_panel.on_editor_open()
    processing.result = False

    control_panel._toggle_processing()
    processing.finish()
    _run_loop(control_panel, lambda: _status(control_panel) == "❌ Échec du traitement IA (voir les logs)")
    assert control_panel._btn_ai.cget("text") == READY


def test_second_click_on_processing_cancels_it(panel):
    """Un second clic déclenche le jeton d'annulation et libère le bouton sans attendre le traitement."""
    control_panel, _, processing = panel
    control_panel.on_editor_open()

    control_panel._toggle_processing()
    _run_loop(control_panel, processing.started.is_set)
    cancel = control_panel._cancel_event
    control_panel._toggle_processing()

    assert cancel is not None and cancel.is_set()
    assert control_panel._btn_ai.cget("text") == READY
    assert _status(control_panel) == "🚫 Traitement annulé"

    # La fin du traitement abandonné ne touche plus l'interface
    _run_loop(control_panel, processing.done.is_set)
    _run_loop_for(control_panel, 0.3)  # Laisser passer la fin du traitement (root.after)
    assert _status(control_panel) == "🚫 Traitement annulé"
    assert processing.calls == 1


# --- Fermeture ---


def test_closing_with_open_editor_closes_it_then_quits(panel, monkeypatch):
    """Avec l'éditeur ouvert, quitter (après confirmation) ferme l'éditeur, attend sa confirmation, puis quitte."""
    control_panel, window, _ = panel
    quits = []
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(control_panel, "_quit", lambda: quits.append(True))
    control_panel.on_editor_open()

    control_panel.on_closing()
    control_panel.on_closing()  # Second clic pendant l'attente : ignoré
    assert window.closes == 1

    control_panel.on_editor_close()  # React confirme la fermeture
    _run_loop(control_panel, lambda: quits == [True])


def test_closing_cancelled_keeps_the_application_open(panel, monkeypatch):
    """Si l'élève renonce à quitter, l'éditeur n'est pas fermé."""
    control_panel, window, _ = panel
    quits = []
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: False)
    monkeypatch.setattr(control_panel, "_quit", lambda: quits.append(True))
    control_panel.on_editor_open()

    control_panel.on_closing()

    assert window.closes == 0
    assert quits == []
