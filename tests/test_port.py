import socket

import askGeminiPrompto as app


def _port_inutilise():
    """Un port que personne n'écoute (réservé puis relâché aussitôt)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("localhost", 0))
        return sock.getsockname()[1]


def test_port_libre_si_personne_n_ecoute():
    """Un port inutilisé est vu comme libre."""
    assert app.port_libre(_port_inutilise())


def test_port_occupe_si_un_programme_ecoute():
    """Un port sur lequel un programme écoute est vu comme occupé (constat B5)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
        serveur.bind(("localhost", 0))
        serveur.listen()
        assert not app.port_libre(serveur.getsockname()[1])


def test_attendre_port_libre_abandonne_apres_le_delai():
    """Si le port reste occupé, l'attente s'arrête et renvoie faux."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
        serveur.bind(("localhost", 0))
        serveur.listen()
        assert not app.attendre_port_libre(serveur.getsockname()[1], delai=1.0)
