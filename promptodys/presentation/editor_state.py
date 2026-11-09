"""État de l'éditeur, tel que le panneau de contrôle le suit : ouvert ou non, en cours d'ouverture,
document courant.

C'est un état de l'interface : seul le thread de l'interface le modifie. Les signaux de React
(threads d'Eel) et les fins de lancement ou de sauvegarde (threads du panneau) lui sont transmis
par ControlPanel._in_ui_thread(). Les autres threads peuvent seulement attendre l'ouverture
de l'éditeur (wait_until_open). N'importe que threading : se teste sans fenêtre Tk.
"""

import threading


class EditorState:
    """
    État de l'éditeur, modifié uniquement par le thread qui l'a créé (celui de l'interface).

    Transitions :
    - start_requested() : clic sur « Ouvrir l'éditeur », renvoie le jeton de ce lancement ;
    - opened()          : React signale que l'éditeur est prêt (on_editor_open) ;
    - closed()          : React signale la fermeture (on_editor_close) ;
    - launch_ended()    : la fenêtre de ce lancement s'est fermée, ou n'a pas pu s'ouvrir.

    Le jeton de lancement écarte la fin tardive d'un lancement remplacé : après la fermeture de Chrome,
    Eel ne rend la main qu'au bout d'une seconde, et l'élève peut avoir relancé l'éditeur entre-temps.

    Un seul threading.Event dit si l'éditeur est ouvert et permet aux autres threads d'attendre son ouverture.
    Les modifications venant d'un autre thread lèvent RuntimeError.
    """

    def __init__(self) -> None:
        # Seul thread autorisé à modifier l'état : celui de l'interface, qui crée le panneau
        self._owner = threading.get_ident()
        # Levé par le signal de React (on_editor_open), baissé à la fermeture de l'éditeur
        self._ready = threading.Event()
        # Du clic sur « Ouvrir l'éditeur » au signal de React (ou à l'échec) : évite un second lancement
        self._starting = False
        # Jeton du dernier lancement demandé, None une fois sa fenêtre fermée
        self._launch: object | None = None
        # Dossier du document courant (style Arduino : mémorise le dernier save/open)
        # Ex: "C:/.../PromptoDYS/MonDoc" → dialogue de sauvegarde pré-rempli.
        # Conservé à la fermeture de l'éditeur.
        self._document_path: str | None = None

    def _check_thread(self) -> None:
        """Refuse une modification venant d'un autre thread que celui de l'interface"""
        if threading.get_ident() != self._owner:
            raise RuntimeError("EditorState ne se modifie que depuis le thread de l'interface")

    @property
    def is_open(self) -> bool:
        """Vrai si React a signalé l'ouverture de l'éditeur, et pas encore sa fermeture"""
        return self._ready.is_set()

    @property
    def is_starting(self) -> bool:
        """Vrai entre le clic sur « Ouvrir l'éditeur » et le signal de React (ou l'échec)"""
        return self._starting

    @property
    def document_path(self) -> str | None:
        """Dossier du document courant, None si aucun document n'a été sauvegardé ni ouvert"""
        return self._document_path

    @document_path.setter
    def document_path(self, path: str | None) -> None:
        self._check_thread()
        self._document_path = path

    def start_requested(self) -> object:
        """Lancement de l'éditeur demandé, en attente du signal de React. Renvoie le jeton de ce lancement,
        à rendre à launch_ended()"""
        self._check_thread()
        self._starting = True
        self._launch = object()
        return self._launch

    def opened(self) -> None:
        """React signale que l'éditeur est prêt : le lancement est terminé"""
        self._check_thread()
        self._starting = False
        self._ready.set()

    def closed(self) -> None:
        """React signale la fermeture de l'éditeur"""
        self._check_thread()
        self._starting = False
        self._ready.clear()

    def launch_ended(self, launch: object) -> bool:
        """La fenêtre du lancement launch s'est fermée, ou n'a pas pu s'ouvrir : l'éditeur est fermé,
        même si React n'a rien signalé (plantage de Chrome). Sans effet si un autre lancement a été
        demandé depuis. Vrai si launch était bien le dernier lancement"""
        self._check_thread()
        if launch is not self._launch:
            return False
        self._launch = None
        self.closed()
        return True

    def wait_until_open(self, timeout: float) -> bool:
        """Attend le signal d'ouverture de React, au plus timeout secondes. Vrai si l'éditeur est ouvert.
        Seule méthode à appeler depuis un autre thread que celui de l'interface"""
        return self._ready.wait(timeout)
