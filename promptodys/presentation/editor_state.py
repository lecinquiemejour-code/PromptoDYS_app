"""État de l'éditeur, tel que le panneau de contrôle le suit : ouvert ou non, en cours d'ouverture,
document courant.

Il est partagé entre trois threads : celui de l'interface (boutons), celui qui lance l'éditeur
et ceux d'Eel (signaux de React). N'importe que threading : se teste sans fenêtre Tk.
"""

import threading


class EditorState:
    """
    État de l'éditeur, partagé entre le thread de l'interface, celui du lancement et ceux d'Eel.

    Transitions :
    - start_requested() : clic sur « Ouvrir l'éditeur », en attente du signal de React ;
    - opened()          : React signale que l'éditeur est prêt (on_editor_open) ;
    - closed()          : React signale la fermeture (on_editor_close), ou la fenêtre s'est fermée
                          sans ce signal (retour ou échec de start(), port pris).

    Un seul threading.Event dit si l'éditeur est ouvert et permet d'attendre son ouverture.
    Pas de verrou : chaque méthode ne fait qu'une ou deux affectations simples.
    """

    def __init__(self) -> None:
        # Levé par le signal de React (on_editor_open), baissé à la fermeture de l'éditeur
        self._ready = threading.Event()
        # Du clic sur « Ouvrir l'éditeur » au signal de React (ou à l'échec) : évite un second lancement
        self._starting = False
        # Dossier du document courant (style Arduino : mémorise le dernier save/open)
        # Ex: "C:/.../PromptoDYS/MonDoc" → dialogue de sauvegarde pré-rempli.
        # Conservé à la fermeture de l'éditeur.
        self.document_path: str | None = None

    @property
    def is_open(self) -> bool:
        """Vrai si React a signalé l'ouverture de l'éditeur, et pas encore sa fermeture"""
        return self._ready.is_set()

    @property
    def is_starting(self) -> bool:
        """Vrai entre le clic sur « Ouvrir l'éditeur » et le signal de React (ou l'échec)"""
        return self._starting

    def start_requested(self) -> None:
        """Lancement de l'éditeur demandé, en attente du signal de React"""
        self._starting = True

    def opened(self) -> None:
        """React signale que l'éditeur est prêt : le lancement est terminé"""
        self._starting = False
        self._ready.set()

    def closed(self) -> None:
        """L'éditeur est fermé (signal de React, fermeture de Chrome, ou échec du lancement)"""
        self._starting = False
        self._ready.clear()

    def wait_until_open(self, timeout: float) -> bool:
        """Attend le signal d'ouverture de React, au plus timeout secondes. Vrai si l'éditeur est ouvert"""
        return self._ready.wait(timeout)
