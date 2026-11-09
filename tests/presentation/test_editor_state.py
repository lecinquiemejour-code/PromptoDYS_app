"""État de l'éditeur, sans fenêtre Tk : transitions et attente du signal de React."""

import threading

from promptodys.presentation.editor_state import EditorState


def test_initial_state_is_closed():
    """Au démarrage, l'éditeur n'est ni ouvert ni en cours d'ouverture, et aucun document n'est mémorisé."""
    state = EditorState()

    assert not state.is_open
    assert not state.is_starting
    assert state.document_path is None


def test_start_open_close():
    """Clic sur « Ouvrir l'éditeur », signal de React, puis fermeture."""
    state = EditorState()

    state.start_requested()
    assert state.is_starting
    assert not state.is_open

    state.opened()
    assert state.is_open
    assert not state.is_starting

    state.closed()
    assert not state.is_open
    assert not state.is_starting


def test_failed_start_ends_the_launch():
    """Un lancement qui échoue (port pris, Chrome absent) n'est plus en cours et l'éditeur reste fermé."""
    state = EditorState()

    state.start_requested()
    state.closed()

    assert not state.is_starting
    assert not state.is_open


def test_wait_until_open_returns_when_react_signals():
    """wait_until_open() rend la main dès que React signale l'ouverture depuis un autre thread."""
    state = EditorState()
    timer = threading.Timer(0.05, state.opened)
    timer.start()

    assert state.wait_until_open(timeout=5)
    timer.join()


def test_wait_until_open_times_out():
    """Sans signal de React, wait_until_open() rend faux au bout du délai."""
    state = EditorState()

    assert not state.wait_until_open(timeout=0.05)


def test_closed_without_react_signal_waits_again():
    """Chrome fermé sans on_editor_close (plantage) : un nouvel éditeur doit de nouveau signaler son ouverture."""
    state = EditorState()
    state.opened()

    state.closed()  # Retour de editor_window.start(), sans signal de React

    assert not state.wait_until_open(timeout=0.05)


def test_document_path_survives_closing():
    """Le document courant est conservé à la fermeture : le dialogue de sauvegarde reste pré-rempli."""
    state = EditorState()
    state.opened()
    state.document_path = "/documents/MonDoc"

    state.closed()

    assert state.document_path == "/documents/MonDoc"
