"""État de l'éditeur, sans fenêtre Tk : transitions, jeton de lancement, thread de l'interface
et attente du signal de React.

Le thread du test joue le rôle du thread de l'interface : c'est lui qui crée l'état."""

import threading

import pytest

from promptodys.presentation.editor_state import EditorState


def test_initial_state_is_closed():
    """Au démarrage, l'éditeur n'est ni ouvert ni en cours d'ouverture, et aucun document n'est mémorisé."""
    state = EditorState()

    assert not state.is_open
    assert not state.is_starting
    assert state.document_path is None


def test_start_open_close():
    """Clic sur « Ouvrir l'éditeur », signal de React, puis fermeture signalée par React."""
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


def test_failed_launch_ends_the_launch():
    """Un lancement qui échoue (port pris, Chrome absent) n'est plus en cours et l'éditeur reste fermé."""
    state = EditorState()

    launch = state.start_requested()

    assert state.launch_ended(launch)
    assert not state.is_starting
    assert not state.is_open


def test_launch_ended_without_react_signal_closes_the_editor():
    """Chrome fermé sans on_editor_close (plantage) : la fin du lancement suffit à fermer l'éditeur,
    et un nouvel éditeur devra de nouveau signaler son ouverture."""
    state = EditorState()
    launch = state.start_requested()
    state.opened()

    assert state.launch_ended(launch)

    assert not state.is_open
    assert not state.wait_until_open(timeout=0.05)


def test_end_of_a_replaced_launch_is_ignored():
    """La fin tardive d'un lancement remplacé par un autre ne touche pas à l'état du nouveau."""
    state = EditorState()
    first = state.start_requested()
    state.opened()
    state.closed()  # React signale la fermeture, Eel n'a pas encore rendu la main
    second = state.start_requested()

    assert not state.launch_ended(first)
    assert state.is_starting

    state.opened()
    assert not state.launch_ended(first)
    assert state.is_open

    assert state.launch_ended(second)
    assert not state.is_open


def test_changes_from_another_thread_are_refused():
    """Seul le thread qui a créé l'état (celui de l'interface) peut le modifier."""
    state = EditorState()
    errors = []

    def change():
        for action in (state.start_requested, state.opened, state.closed, lambda: state.launch_ended(object())):
            try:
                action()
            except RuntimeError as e:
                errors.append(e)
        try:
            state.document_path = "/documents/MonDoc"
        except RuntimeError as e:
            errors.append(e)

    thread = threading.Thread(target=change)
    thread.start()
    thread.join()

    assert len(errors) == 5
    assert not state.is_open
    assert not state.is_starting
    assert state.document_path is None


def test_wait_until_open_from_another_thread():
    """Un autre thread attend l'ouverture, signalée sur le thread de l'interface."""
    state = EditorState()
    results = []
    thread = threading.Thread(target=lambda: results.append(state.wait_until_open(timeout=5)))
    thread.start()

    state.opened()
    thread.join()

    assert results == [True]


def test_wait_until_open_times_out():
    """Sans signal de React, wait_until_open() rend faux au bout du délai."""
    state = EditorState()

    assert not state.wait_until_open(timeout=0.05)


def test_document_path_survives_closing():
    """Le document courant est conservé à la fermeture : le dialogue de sauvegarde reste pré-rempli."""
    state = EditorState()
    state.opened()
    state.document_path = "/documents/MonDoc"

    state.closed()

    assert state.document_path == "/documents/MonDoc"


@pytest.mark.parametrize("path", [None, "/documents/MonDoc"])
def test_document_path_set_from_the_ui_thread(path):
    """Le thread de l'interface peut mémoriser un document, ou l'oublier."""
    state = EditorState()

    state.document_path = path

    assert state.document_path == path
