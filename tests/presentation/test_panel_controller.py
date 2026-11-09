"""Logique du panneau de contrôle (PanelController), avec une vue, un éditeur, un rangement, une fenêtre
de l'éditeur et un traitement simulés. Aucune fenêtre Tk : plusieurs Tk dans un même processus échouent
au hasard sur la CI Windows.

Les threads du contrôleur sont de vrais threads. Ils passent par view.after(), que la vue simulée range
dans une file : _pump_until() la vide dans le thread du test, qui joue le rôle du thread de l'interface
(celui qui a construit le contrôleur, seul autorisé à modifier EditorState).

view.quit() est seulement enregistré : os._exit n'est jamais appelé ni remplacé (pytest-timeout en a besoin
pour arrêter un test bloqué sous Windows).
"""

import os
import threading
import time

import pytest

import promptodys.presentation.panel_controller as controller_module
from promptodys.domain import ports
from promptodys.presentation.panel_controller import PanelController


class _View:
    """Vue simulée : enregistre ce que le contrôleur affiche et répond aux dialogues comme réglé.
    after() range les fonctions dans une file, exécutée par run_pending() dans le thread du test."""

    def __init__(self):
        self.statuses = []
        self.processing = False
        self.console_cleared = 0
        self.refreshes = 0
        self.errors = []
        self.warnings = []
        self.questions = []
        self.quits = 0
        self.yes_no_answer = True
        self.open_path = ""
        self.save_paths = []  # Réponses successives au dialogue d'enregistrement
        self.save_dialogs = []  # (initial_dir, initial_name) de chaque dialogue d'enregistrement
        self._pending = []
        self._lock = threading.Lock()  # after() est appelé depuis les threads du contrôleur

    @property
    def status(self):
        return self.statuses[-1] if self.statuses else None

    def show_status(self, text):
        self.statuses.append(text)

    def set_processing(self, running):
        self.processing = running

    def clear_console(self):
        self.console_cleared += 1

    def refresh(self):
        self.refreshes += 1

    def show_error(self, title, message):
        self.errors.append(message)

    def show_warning(self, title, message):
        self.warnings.append(message)

    def ask_yes_no(self, title, message):
        self.questions.append(message)
        return self.yes_no_answer

    def ask_open_path(self, initial_dir):
        return self.open_path

    def ask_save_path(self, initial_dir, initial_name):
        self.save_dialogs.append((initial_dir, initial_name))
        return self.save_paths.pop(0) if self.save_paths else ""

    def after(self, delay_ms, fn):
        with self._lock:
            self._pending.append(fn)

    def quit(self):
        self.quits += 1

    def run_pending(self):
        """Exécute les fonctions déjà en file (pas celles qu'elles ajoutent), dans le thread du test"""
        with self._lock:
            pending, self._pending = self._pending, []
        for fn in pending:
            fn()


class _Editor:
    """Éditeur simulé : enregistre les documents qu'on lui envoie, renvoie toujours la même note."""

    document = ports.Document(markdown="# Ma note")

    def __init__(self):
        self.written = []

    def write_document(self, document):
        self.written.append(document)
        return True

    def read_document(self):
        return self.document


class _Store:
    """Rangement simulé : tout chemin désigne le même document, rangé dans le dossier du chemin."""

    document = ports.Document(markdown="# Ma note")

    def __init__(self):
        self.saved = []

    def load(self, path):
        return self.document, os.path.dirname(path)

    def save(self, document, directory, name):
        self.saved.append((directory, name))
        return os.path.join(directory, name)


class _Window:
    """Fenêtre de l'éditeur simulée : start() bloque, comme Chrome jusqu'à sa fermeture.
    release() fait se terminer tous les start(), présents et à venir ; end_start(i) seulement le i-ième."""

    port = 8080

    def __init__(self):
        self.port_free = True
        self.close_error = None  # Exception levée par close(), None si la demande part
        self.starts = 0
        self.ended = 0  # Nombre de start() terminés
        self.closes = 0
        self.started = threading.Event()
        self._all_released = False
        self._ends = []  # Un Event par appel de start()

    def wait_for_free_port(self):
        return self.port_free

    def start(self):
        end = threading.Event()
        self._ends.append(end)
        self.starts += 1
        self.started.set()
        if not self._all_released:
            end.wait(timeout=5)
        self.ended += 1

    def close(self):
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error

    def end_start(self, index):
        """Fait se terminer le index-ième start(), comme à la fermeture de cette fenêtre Chrome"""
        self._ends[index].set()

    def release(self):
        """Fait se terminer tous les start(), y compris ceux qui n'ont pas encore commencé"""
        self._all_released = True
        for end in self._ends:
            end.set()


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


class _Panel:
    """Contrôleur et ses simulations, construits dans le thread du test"""

    def __init__(self, documents_dir):
        self.view = _View()
        self.editor = _Editor()
        self.store = _Store()
        self.window = _Window()
        self.processing = _Processing()
        self.controller = PanelController(
            view=self.view,
            editor=self.editor,
            store=self.store,
            editor_window=self.window,
            process_note=self.processing,
            documents_dir=documents_dir,
        )

    @property
    def state(self):
        return self.controller._editor_state


@pytest.fixture
def panel(tmp_path):
    p = _Panel(str(tmp_path))
    yield p
    p.window.release()  # Ne pas laisser un thread bloqué dans start()
    p.processing.finish()


def _pump_until(view, condition, timeout=3.0):
    """Exécute la file de view.after() jusqu'à ce que condition() soit vraie (au plus timeout secondes)"""
    deadline = time.monotonic() + timeout
    while True:
        view.run_pending()
        if condition() or time.monotonic() > deadline:
            break
        time.sleep(0.01)
    assert condition()


def _pump_for(view, seconds):
    """Exécute la file de view.after() pendant une durée fixe (laisse passer les fins venant des threads)"""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        view.run_pending()
        time.sleep(0.01)


def _react_signals_open(panel):
    """React signale l'ouverture (depuis un thread d'Eel en vrai) ; le thread de l'interface applique le signal"""
    panel.controller.on_editor_open()
    panel.view.run_pending()


# --- Événements de React ---


def test_react_events_update_state_and_status(panel):
    """on_editor_open et on_editor_close mettent à jour l'état de l'éditeur et la barre de statut,
    par le thread de l'interface."""
    panel.controller.on_editor_open()
    assert not panel.state.is_open  # Rien tant que le thread de l'interface n'a pas exécuté le signal
    panel.view.run_pending()
    assert panel.state.is_open
    assert panel.view.status == "✅ Éditeur ouvert"

    panel.controller.on_editor_close()
    panel.view.run_pending()
    assert not panel.state.is_open
    assert panel.view.status == "🔴 Éditeur fermé"


# --- Ouverture de l'éditeur ---


def test_second_click_on_open_editor_launches_nothing(panel):
    """Pendant le lancement puis une fois l'éditeur ouvert, un nouveau clic ne relance pas l'éditeur."""
    panel.controller.open_editor()
    _pump_until(panel.view, panel.window.started.is_set)
    panel.controller.open_editor()
    assert panel.view.status == "⏳ Ouverture de l'éditeur en cours, veuillez patienter"

    _react_signals_open(panel)
    panel.controller.open_editor()
    assert panel.view.status == "✅ L'éditeur est déjà ouvert"
    assert panel.window.starts == 1

    # Fermeture de Chrome : start() retourne, l'éditeur est vu fermé
    panel.window.release()
    _pump_until(
        panel.view,
        lambda: panel.view.status == "🔴 Éditeur fermé" and not panel.state.is_open and not panel.state.is_starting,
    )


def test_late_end_of_a_replaced_launch_is_ignored(panel):
    """Chrome fermé puis éditeur relancé aussitôt : la fin tardive du premier lancement (Eel rend la main
    une seconde après la fermeture) ne touche pas au second, et un nouveau clic ne relance rien."""
    # Premier éditeur ouvert, puis fermé par l'élève : React le signale, start() n'a pas encore rendu la main
    panel.controller.open_editor()
    _pump_until(panel.view, panel.window.started.is_set)
    _react_signals_open(panel)
    panel.controller.on_editor_close()
    panel.view.run_pending()

    # Relance immédiate
    panel.controller.open_editor()
    _pump_until(panel.view, lambda: panel.window.starts == 2)

    # Le premier start() rend la main : sa fin est ignorée
    panel.window.end_start(0)
    _pump_until(panel.view, lambda: panel.window.ended == 1)
    _pump_for(panel.view, 0.2)  # Laisser passer la fin du premier lancement
    assert panel.state.is_starting
    assert panel.view.status == "⏳ Ouverture de l'éditeur en cours, veuillez patienter"

    panel.controller.open_editor()
    assert panel.window.starts == 2

    # Le second éditeur s'ouvre, puis se ferme
    _react_signals_open(panel)
    assert panel.state.is_open
    panel.window.end_start(1)
    _pump_until(panel.view, lambda: panel.view.status == "🔴 Éditeur fermé")
    assert not panel.state.is_open


def test_busy_port_opens_no_editor(panel):
    """Si le port reste occupé, l'éditeur n'est pas lancé et l'élève est prévenu."""
    panel.window.port_free = False

    panel.controller.open_editor()
    _pump_until(panel.view, lambda: panel.view.errors != [])

    assert panel.window.starts == 0
    assert panel.view.status == "❌ Port 8080 déjà utilisé par un autre programme"
    assert not panel.state.is_starting


# --- Ouverture d'un document ---


def test_open_document_launches_editor_then_loads_it(panel, tmp_path, monkeypatch):
    """Éditeur fermé : « Ouvrir » lance l'éditeur, attend le signal de React, puis charge le document."""
    document_dir = tmp_path / "MonDoc"
    panel.view.open_path = str(document_dir / "MonDoc.md")
    monkeypatch.setattr(controller_module, "REACT_SETTLE_DELAY_S", 0)

    panel.controller.open_document()
    _pump_until(panel.view, panel.window.started.is_set)
    assert panel.editor.written == []  # Rien n'est envoyé avant le signal de React

    _react_signals_open(panel)
    _pump_until(panel.view, lambda: panel.view.status == "✅ 'MonDoc' ouvert !")
    assert panel.editor.written == [_Store.document]
    assert panel.state.document_path == str(document_dir)
    assert panel.window.starts == 1


def test_open_document_with_open_editor_loads_it_at_once(panel, tmp_path):
    """Éditeur déjà ouvert : « Ouvrir » charge le document sans relancer l'éditeur ni attendre."""
    panel.view.open_path = str(tmp_path / "MonDoc" / "MonDoc.md")
    _react_signals_open(panel)

    panel.controller.open_document()
    _pump_until(panel.view, lambda: panel.view.status == "✅ 'MonDoc' ouvert !")
    assert panel.editor.written == [_Store.document]
    assert panel.window.starts == 0


def test_open_document_cancelled_does_nothing(panel):
    """Dialogue annulé : ni lancement de l'éditeur, ni chargement."""
    panel.controller.open_document()

    assert panel.window.starts == 0
    assert panel.view.statuses == []


def test_open_document_after_chrome_crash_waits_for_react(panel, tmp_path, monkeypatch):
    """Chrome fermé sans signal de React (plantage) : « Ouvrir » attend de nouveau le signal de React,
    et sans lui n'envoie rien à l'éditeur."""
    panel.view.open_path = str(tmp_path / "MonDoc" / "MonDoc.md")
    monkeypatch.setattr(controller_module, "REACT_SETTLE_DELAY_S", 0)
    monkeypatch.setattr(controller_module, "EDITOR_READY_TIMEOUT_S", 0.2)

    # Premier éditeur : ouvert, puis Chrome se ferme sans on_editor_close
    panel.controller.open_editor()
    _pump_until(panel.view, panel.window.started.is_set)
    _react_signals_open(panel)
    panel.window.release()
    _pump_until(panel.view, lambda: not panel.state.is_open)

    # Le nouvel éditeur ne signale jamais son ouverture
    panel.controller.open_document()
    _pump_until(
        panel.view,
        lambda: panel.view.status == "❌ Éditeur non prêt (timeout)" and not panel.state.is_starting,
    )
    assert panel.editor.written == []
    assert panel.window.starts == 2


# --- Sauvegarde ---


def test_save_requires_an_open_editor(panel):
    """Sans éditeur ouvert, aucun dialogue : l'élève est prévenu."""
    panel.controller.save_document()

    assert len(panel.view.warnings) == 1
    assert panel.view.save_dialogs == []
    assert panel.view.status == "⚠️ Éditeur non ouvert"


def test_save_stores_the_document_and_remembers_its_folder(panel, tmp_path):
    """Le document est rangé sous le nom choisi ; le dialogue suivant part de son dossier."""
    _react_signals_open(panel)
    panel.view.save_paths = [str(tmp_path / "MaNote")]

    panel.controller.save_document()
    _pump_until(panel.view, lambda: panel.view.status == "✅ 'MaNote' sauvegardé !")
    assert panel.view.save_dialogs == [(str(tmp_path), "nouveau_document")]
    assert panel.store.saved == [(str(tmp_path), "MaNote")]
    assert panel.state.document_path == str(tmp_path / "MaNote")

    panel.controller.save_document()  # Annulé (aucune réponse réglée)
    assert panel.view.save_dialogs[-1] == (str(tmp_path), "MaNote")


def test_save_with_an_invalid_name_reopens_the_dialog(panel, tmp_path):
    """Nom vide après assainissement : avertissement, puis le dialogue se rouvre."""
    _react_signals_open(panel)
    panel.view.save_paths = [str(tmp_path / ".cache"), str(tmp_path / "MaNote")]

    panel.controller.save_document()
    _pump_until(panel.view, lambda: panel.view.status == "✅ 'MaNote' sauvegardé !")
    assert len(panel.view.warnings) == 1
    assert len(panel.view.save_dialogs) == 2
    assert panel.store.saved == [(str(tmp_path), "MaNote")]


# --- Traitement IA ---


def test_processing_requires_an_open_editor(panel):
    """Sans éditeur ouvert, le traitement n'est pas lancé et l'élève est prévenu."""
    panel.controller.toggle_processing()

    assert len(panel.view.warnings) == 1
    assert panel.processing.calls == 0
    assert panel.view.status == "⚠️ Éditeur non ouvert"


def test_completed_processing_resets_the_button(panel):
    """Un traitement abouti vide la console au lancement, puis remet le bouton à l'état Prêt."""
    _react_signals_open(panel)

    panel.controller.toggle_processing()
    assert panel.view.processing
    assert panel.view.console_cleared == 1
    _pump_until(panel.view, panel.processing.started.is_set)

    panel.processing.finish()
    _pump_until(panel.view, lambda: panel.view.status == "✅ Traitement IA terminé !")
    assert not panel.view.processing  # Bouton « 🤖 Traiter la prise de note »
    assert panel.controller._cancel_event is None


def test_failed_processing_shows_failure(panel):
    """Un traitement en échec remet le bouton à l'état Prêt et renvoie aux logs."""
    _react_signals_open(panel)
    panel.processing.result = False

    panel.controller.toggle_processing()
    panel.processing.finish()
    _pump_until(panel.view, lambda: panel.view.status == "❌ Échec du traitement IA (voir les logs)")
    assert not panel.view.processing  # Bouton « 🤖 Traiter la prise de note »


def test_second_click_on_processing_cancels_it(panel):
    """Un second clic déclenche le jeton d'annulation et libère le bouton sans attendre le traitement."""
    _react_signals_open(panel)

    panel.controller.toggle_processing()
    _pump_until(panel.view, panel.processing.started.is_set)
    cancel = panel.controller._cancel_event
    panel.controller.toggle_processing()

    assert cancel is not None and cancel.is_set()
    assert not panel.view.processing  # Bouton « 🤖 Traiter la prise de note »
    assert panel.view.status == "🚫 Traitement annulé"

    # La fin du traitement abandonné ne touche plus l'interface
    _pump_until(panel.view, panel.processing.done.is_set)
    _pump_for(panel.view, 0.3)  # Laisser passer la fin du traitement
    assert panel.view.status == "🚫 Traitement annulé"
    assert panel.processing.calls == 1


# --- Fermeture ---


def test_closing_without_editor_quits_at_once(panel):
    """Sans éditeur ouvert, quitter ne demande rien."""
    panel.controller.on_closing()

    assert panel.view.questions == []
    assert panel.view.quits == 1


def test_closing_with_open_editor_closes_it_then_quits(panel):
    """Avec l'éditeur ouvert, quitter (après confirmation) ferme l'éditeur, attend sa confirmation, puis quitte."""
    _react_signals_open(panel)

    panel.controller.on_closing()
    panel.controller.on_closing()  # Second clic pendant l'attente : ignoré
    assert panel.window.closes == 1
    assert len(panel.view.questions) == 1

    panel.view.run_pending()
    assert panel.view.quits == 0  # Pas avant la confirmation de l'éditeur

    panel.controller.on_editor_close()  # React confirme la fermeture
    _pump_until(panel.view, lambda: panel.view.quits == 1)


def test_closing_quits_anyway_if_the_editor_does_not_confirm(panel, monkeypatch):
    """Si l'éditeur ne confirme pas sa fermeture dans le délai, on quitte quand même."""
    monkeypatch.setattr(controller_module, "CLOSE_EDITOR_TIMEOUT_S", 0)
    _react_signals_open(panel)

    panel.controller.on_closing()
    _pump_until(panel.view, lambda: panel.view.quits == 1)
    assert panel.state.is_open


def test_closing_quits_at_once_if_the_close_request_fails(panel):
    """Si la demande de fermeture ne peut pas partir (bundle sans closeEditor), on quitte tout de suite."""
    panel.window.close_error = RuntimeError("closeEditor absent")
    _react_signals_open(panel)

    panel.controller.on_closing()

    assert panel.view.quits == 1


def test_closing_cancelled_keeps_the_application_open(panel):
    """Si l'élève renonce à quitter, l'éditeur n'est pas fermé."""
    panel.view.yes_no_answer = False
    _react_signals_open(panel)

    panel.controller.on_closing()

    assert panel.window.closes == 0
    assert panel.view.quits == 0
