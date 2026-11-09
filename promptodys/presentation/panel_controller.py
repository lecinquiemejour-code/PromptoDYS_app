"""Logique du panneau de contrôle, sans Tk : ouvrir l'éditeur, sauvegarder et ouvrir un document,
lancer ou abandonner le traitement IA, quitter.

- PanelController : réagit aux boutons et aux signaux de React, lance les threads et tient l'état
  (EditorState, traitement en cours, fermeture demandée) ;
- PanelView : ce que le contrôleur demande à la fenêtre (ControlPanel, la vue Tk) ;
- EditorWindow : ce que le contrôleur attend de la fenêtre de l'éditeur (EelWindow dans l'infrastructure).

N'importe ni tkinter ni sv_ttk (contrat import-linter) : se teste avec une vue simulée, sans fenêtre Tk.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Protocol

from promptodys.domain import documents, ports
from promptodys.presentation.editor_state import EditorState

_logger = logging.getLogger(__name__)

# Délai maximum d'attente de la fermeture de l'éditeur avant de quitter quand même
CLOSE_EDITOR_TIMEOUT_S = 3
# Délai maximum d'attente du signal de React (on_editor_open) avant d'ouvrir un document
EDITOR_READY_TIMEOUT_S = 30
# Après le signal de React, laisse l'éditeur finir d'initialiser ses composants
REACT_SETTLE_DELAY_S = 1.5


class EditorWindow(Protocol):
    """Fenêtre de l'éditeur, ouverte et fermée par le panneau (EelWindow dans l'infrastructure)"""

    port: int

    def wait_for_free_port(self) -> bool:
        """Attend que le port de l'éditeur se libère, faux s'il reste occupé"""
        ...

    def start(self) -> None:
        """Ouvre l'éditeur et bloque jusqu'à sa fermeture ; lève une exception en cas d'échec"""
        ...

    def close(self) -> None:
        """Demande la fermeture de l'éditeur ; lève une exception si la demande n'a pas pu partir"""
        ...


class PanelView(Protocol):
    """Fenêtre du panneau, telle que le contrôleur la pilote (ControlPanel, la vue Tk).
    Toutes ces méthodes, sauf after(), s'appellent depuis le thread de l'interface."""

    def show_status(self, text: str) -> None:
        """Affiche text dans la barre de statut"""
        ...

    def set_processing(self, running: bool) -> None:
        """Bouton du traitement IA : « Abandonner » pendant un traitement, « Traiter » sinon"""
        ...

    def clear_console(self) -> None:
        """Vide la console, dans l'ordre des messages qui y sont déjà en attente"""
        ...

    def refresh(self) -> None:
        """Affiche tout de suite les changements, avant une étape qui peut faire attendre"""
        ...

    def show_error(self, title: str, message: str) -> None:
        """Popup d'erreur"""
        ...

    def show_warning(self, title: str, message: str) -> None:
        """Popup d'avertissement"""
        ...

    def ask_yes_no(self, title: str, message: str) -> bool:
        """Question oui/non, vrai si l'élève répond oui"""
        ...

    def ask_open_path(self, initial_dir: str) -> str:
        """Dialogue d'ouverture d'un document : chemin choisi, chaîne vide si annulé"""
        ...

    def ask_save_path(self, initial_dir: str, initial_name: str) -> str:
        """Dialogue d'enregistrement d'un document : chemin choisi, chaîne vide si annulé"""
        ...

    def after(self, delay_ms: int, fn: Callable[[], object]) -> None:
        """Fait exécuter fn par le thread de l'interface après delay_ms ; appelable depuis n'importe quel thread"""
        ...

    def quit(self) -> None:
        """Ferme le panneau et termine le processus"""
        ...


class PanelController:
    """
    Logique du panneau de contrôle. Les boutons de la vue appellent open_editor(), save_document(),
    open_document(), toggle_processing() et on_closing() ; Eel appelle on_editor_open() et on_editor_close().

    L'état de l'éditeur (_editor_state, voir EditorState) est géré exclusivement par les événements
    de React et par le retour de editor_window.start(), et modifié uniquement par le thread de
    l'interface (les autres threads passent par _in_ui_thread) :
    - open_editor()     : lancement demandé (start_requested), qui reçoit son jeton ;
    - on_editor_open()  : React notifie l'ouverture (opened), fin du lancement ;
    - on_editor_close() : React notifie la fermeture (closed) ;
    - _launch_editor()  : port pris, editor_window.start() qui retourne ou qui lève (launch_ended),
                          sans effet si un autre lancement a été demandé depuis.

    À construire depuis le thread de l'interface : c'est le seul autorisé à modifier l'état.
    """

    def __init__(
        self,
        view: PanelView,
        editor: ports.Editor,
        store: ports.DocumentStore,
        editor_window: EditorWindow,
        process_note: Callable[[threading.Event], bool],
        documents_dir: str,
    ) -> None:
        self._view = view
        self._editor = editor
        self._store = store
        self._editor_window = editor_window
        self._process_note = process_note
        self._documents_dir = documents_dir

        # --- État de l'éditeur (modifié par le thread de l'interface seulement, qui construit le contrôleur) ---
        self._editor_state = EditorState()
        # Fermeture de l'éditeur demandée, en attente de sa confirmation : ignore un second clic sur Quitter
        self._closing = False

        # --- État du traitement IA ---
        # Jeton d'annulation du traitement IA en cours, None si aucun traitement en cours
        self._cancel_event: threading.Event | None = None

    # --- Accès au thread de l'interface ---

    def _in_ui_thread(self, fn: Callable[[], object]) -> None:
        """Fait exécuter fn par le thread de l'interface : seul passage autorisé depuis les autres threads
        (Tkinter n'est pas thread-safe). La file d'attente prévue par R7 ne changera que cette méthode."""
        self._view.after(0, fn)

    # --- Événements de React (appelés depuis un thread d'Eel) ---

    def on_editor_open(self) -> None:
        """React signale que l'éditeur est prêt. État et statut sont mis à jour par le thread de l'interface"""

        def _opened() -> None:
            self._editor_state.opened()
            self._view.show_status("✅ Éditeur ouvert")

        self._in_ui_thread(_opened)

    def on_editor_close(self) -> None:
        """React signale la fermeture de l'éditeur. État et statut sont mis à jour par le thread de l'interface"""

        def _closed() -> None:
            self._editor_state.closed()
            self._view.show_status("🔴 Éditeur fermé")

        self._in_ui_thread(_closed)

    # --- Boutons ---

    def open_editor(self) -> None:
        """Lance l'éditeur dans un thread séparé"""
        if self._editor_state.is_open:
            _logger.info("📝 L'éditeur est déjà ouvert")
            self._view.show_status("✅ L'éditeur est déjà ouvert")
            return

        if self._editor_state.is_starting:
            _logger.info("📝 L'éditeur est déjà en cours d'ouverture")
            self._view.show_status("⏳ Ouverture de l'éditeur en cours, veuillez patienter")
            return

        # Dès le clic : un second clic pendant l'attente du port ou de Chrome ne relance rien
        launch = self._editor_state.start_requested()
        _logger.info("📝 Action: Lancement de l'éditeur...")
        self._view.show_status("⏳ Ouverture de l'éditeur en cours, veuillez patienter")
        self._view.refresh()

        # Lancer dans un thread pour ne pas bloquer la GUI
        thread = threading.Thread(target=self._launch_editor, args=(launch,), daemon=True)
        thread.start()
        # « ✅ Éditeur ouvert » est affiché par on_editor_open(), quand React signale que l'éditeur est prêt

    def _end_launch(self, launch: object, status: str, error: str | None = None) -> None:
        """Fin du lancement launch (fenêtre fermée ou jamais ouverte) : état, statut et, en cas d'échec,
        popup, par le thread de l'interface. Ignorée si un autre lancement a été demandé depuis :
        elle décrirait une fenêtre qui n'est plus celle de l'élève."""

        def _end() -> None:
            if not self._editor_state.launch_ended(launch):
                return
            self._view.show_status(status)
            if error is not None:
                self._view.show_error("PromptoDYS - Éditeur non ouvert", error)

        self._in_ui_thread(_end)

    def _launch_editor(self, launch: object) -> None:
        """Ouvre l'éditeur (thread dédié) et attend sa fermeture. launch : jeton de ce lancement"""
        port = self._editor_window.port
        # Vérifier le port avant d'ouvrir Chrome : s'il est pris, Chrome afficherait
        # la page de l'autre programme. On n'ouvre alors aucune fenêtre.
        if not self._editor_window.wait_for_free_port():
            _logger.info(f"❌ Le port {port} est utilisé par un autre programme : éditeur non ouvert")
            self._end_launch(
                launch,
                f"❌ Port {port} déjà utilisé par un autre programme",
                f"Un autre programme utilise le port {port},\n"
                "nécessaire à l'éditeur.\n\n"
                "Fermez les autres programmes ouverts,\n"
                "ou redémarrez l'ordinateur, puis réessayez.",
            )
            return
        try:
            # Bloque jusqu'à la fermeture de l'éditeur (mode de secours compris)
            self._editor_window.start()
        except Exception as e:
            _logger.info(f"❌ Erreur fallback lancement éditeur: {e}")
            self._end_launch(
                launch,
                "❌ Échec de l'ouverture de l'éditeur (voir les logs)",
                "L'éditeur n'a pas pu s'ouvrir.\n\n"
                "Vérifiez que Google Chrome est installé,\n"
                "puis réessayez.\n\n"
                "Le détail de l'erreur est dans la console.",
            )
            return

        # Quand l'éditeur se ferme, on met à jour le statut. L'état est remis à « fermé » même si
        # React n'a jamais signalé l'ouverture, ou n'a pas signalé la fermeture (plantage de Chrome)
        self._end_launch(launch, "🔴 Éditeur fermé")

    def save_document(self) -> None:
        """Sauvegarde le document — toujours en mode "Enregistrer sous" (dialogue à chaque fois).
        Si un document est déjà ouvert, le dialogue pré-remplit le nom et le dossier courant."""
        if not self._editor_state.is_open:
            self._view.show_warning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\nVeuillez d'abord ouvrir l'éditeur\navant de sauvegarder.",
            )
            self._view.show_status("⚠️ Éditeur non ouvert")
            return

        _logger.info(
            f"🔍 DEBUG btn_sauvegarder: editeur_lance={self._editor_state.is_open}, "
            f"current_document_path={self._editor_state.document_path}"
        )

        # Toujours afficher le dialogue — pré-rempli si document déjà ouvert/sauvegardé
        current_path = self._editor_state.document_path
        initial_dir = os.path.dirname(current_path) if current_path else self._documents_dir
        initial_name = os.path.basename(current_path) if current_path else "nouveau_document"

        # Le dialogue se rouvre tant que le nom saisi est vide après assainissement
        while True:
            selected = self._view.ask_save_path(initial_dir, initial_name)
            if not selected:
                _logger.info("💾 Sauvegarde annulée par l'utilisateur")
                return

            save_dir, doc_name = documents.prepare_save_path(selected)
            if doc_name:
                break

            _logger.info(f"⚠️ Nom de document invalide: '{os.path.basename(selected)}'")
            self._view.show_warning(
                "PromptoDYS - Nom invalide",
                "Le nom du document est vide\n"
                "ou commence par un point.\n\n"
                "Veuillez saisir un nom\n"
                "(lettres ou chiffres).",
            )
            initial_dir = os.path.dirname(selected)
            initial_name = "nouveau_document"

        self._view.show_status("⏳ Sauvegarde en cours...")
        self._view.refresh()

        def run_save() -> None:
            _logger.info(f"🔍 DEBUG run_save: doc_name='{doc_name}', save_dir='{save_dir}'")
            result = documents.save_document(self._editor, self._store, save_dir, doc_name)
            if result:

                def _saved() -> None:
                    self._editor_state.document_path = result
                    self._view.show_status(f"✅ '{doc_name}' sauvegardé !")

                self._in_ui_thread(_saved)
                _logger.info(f"✅ Document sauvegardé dans: {result}")
            else:
                self._in_ui_thread(lambda: self._view.show_status("❌ Erreur de sauvegarde"))

        thread = threading.Thread(target=run_save, daemon=True)
        thread.start()

    def open_document(self) -> None:
        """Ouvre un document complet (texte + images) via le dialogue — accepte dossier ou fichier .md
        Si l'éditeur n'est pas lancé, il est ouvert automatiquement avant le chargement."""
        # 1. Choisir le fichier AVANT de lancer l'éditeur (le dialogue est indépendant)
        selected_path = self._view.ask_open_path(self._documents_dir)
        if not selected_path:
            _logger.info("📂 Ouverture annulée par l'utilisateur")
            return

        # 2. Si l'éditeur n'est pas ouvert, le lancer automatiquement
        need_wait = not self._editor_state.is_open
        if need_wait:
            _logger.info("📂 Éditeur non ouvert → lancement automatique avant ouverture du document...")
            self._view.show_status("⏳ Lancement de l'éditeur...")
            self._view.refresh()
            self.open_editor()

        self._view.show_status("⏳ Ouverture en cours...")
        self._view.refresh()

        # 3. Attendre que l'éditeur soit prêt, puis charger le document
        def run_load() -> None:
            if need_wait:
                # Attendre le signal de React (on_editor_open)
                _logger.info("⏳ Attente du signal React on_editor_open()...")
                if not self._editor_state.wait_until_open(EDITOR_READY_TIMEOUT_S):
                    _logger.info(
                        f"❌ Timeout: React n'a pas signalé on_editor_open() dans les {EDITOR_READY_TIMEOUT_S} secondes"
                    )
                    self._in_ui_thread(lambda: self._view.show_status("❌ Éditeur non prêt (timeout)"))
                    return

                # Petit délai pour laisser React finir l'initialisation complète des composants
                time.sleep(REACT_SETTLE_DELAY_S)

            _logger.info("✅ Éditeur prêt, chargement du document...")

            result = documents.open_document(self._editor, self._store, selected_path)
            if result:
                doc_name = os.path.basename(result)
                _logger.info(f"📌 Document courant: {result}")

                def _opened() -> None:
                    # Mémoriser le dossier du document ouvert (comme Arduino retient le sketch ouvert)
                    self._editor_state.document_path = result
                    self._view.show_status(f"✅ '{doc_name}' ouvert !")

                self._in_ui_thread(_opened)
            else:
                self._in_ui_thread(lambda: self._view.show_status("❌ Erreur d'ouverture"))

        thread = threading.Thread(target=run_load, daemon=True)
        thread.start()

    def toggle_processing(self) -> None:
        """Lance le traitement IA Gemini ou demande l'abandon"""
        # SI DÉJÀ EN COURS -> ABANDON IMMÉDIAT
        # Le thread de traitement ne peut pas être interrompu s'il attend Gemini :
        # on déclenche son jeton et on libère l'interface sans l'attendre.
        # S'il se réveille plus tard, il voit son jeton déclenché et s'arrête sans rien écrire.
        if self._cancel_event is not None:
            _logger.info("\n🚫 ABANDON: Traitement IA arrêté par l'utilisateur.")
            self._cancel_event.set()
            self._cancel_event = None
            self._view.set_processing(False)
            self._view.show_status("🚫 Traitement annulé")
            return

        # VÉRIFICATION 1: Connexion internet - SUPPRIMÉE
        _logger.info("\n🔍 VÉRIFICATION PRÉ-TRAITEMENT IA...")

        # VÉRIFICATION 2: Éditeur ouvert
        if not self._editor_state.is_open:
            _logger.info("⚠️ L'éditeur n'est pas ouvert !")
            self._view.show_warning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\nVeuillez d'abord ouvrir l'éditeur\navant de lancer le traitement IA.",
            )
            self._view.show_status("⚠️ Éditeur non ouvert")
            return

        _logger.info("🤖 Action: Lancement du traitement IA...")
        self._view.show_status("⏳ Traitement IA en cours...")

        # Nouveau jeton d'annulation, propre à ce traitement. Il est enregistré AVANT refresh()
        # et le thread, pour qu'un second clic soit traité comme une demande d'abandon
        cancel = threading.Event()
        self._cancel_event = cancel

        # Mise à jour du bouton en mode "Abandon"
        self._view.set_processing(True)
        self._view.refresh()

        # Nouveau traitement : console vidée AVANT le premier log du traitement. L'effacement passe
        # par la même file que l'affichage : les logs du thread s'afficheront après lui
        self._view.clear_console()

        def finish(success: bool) -> None:
            """Fin du traitement, exécutée sur le thread de l'interface (via _in_ui_thread)"""
            # Traitement abandonné (et peut-être remplacé par un autre) : l'interface est déjà à jour
            if self._cancel_event is not cancel:
                return
            self._cancel_event = None
            _logger.info("🔄 FIN: Réinitialisation du bouton de contrôle")
            self._view.set_processing(False)
            if success:
                self._view.show_status("✅ Traitement IA terminé !")
            else:
                self._view.show_status("❌ Échec du traitement IA (voir les logs)")

        # Lancer le traitement dans un thread pour ne pas bloquer la GUI
        # Ce thread ne modifie aucune variable d'état : il confie la fin au thread de l'interface
        def run_processing() -> None:
            success = False
            try:
                success = self._process_note(cancel)
            except Exception as e:
                if not cancel.is_set():
                    _logger.info(f"❌ Erreur critique IA: {e}")
            finally:
                self._in_ui_thread(lambda: finish(success))

        thread = threading.Thread(target=run_processing, daemon=True)
        thread.start()

    # --- Fermeture ---

    def _close_editor_then_quit(self) -> None:
        """
        Demande à l'éditeur React de fermer sa fenêtre (closeEditor), attend sa confirmation
        (on_editor_close ou retour de editor_window.start() marquent l'éditeur fermé), puis quitte.
        Sous Windows, Chrome s'arrête avec sa dernière fenêtre. Au-delà du délai, on quitte quand même.
        """
        _logger.info("📝 Fermeture de l'éditeur...")
        try:
            self._editor_window.close()
        except Exception as e:
            # Bundle sans closeEditor, ou connexion déjà fermée
            _logger.info(f"⚠️ Impossible de demander la fermeture de l'éditeur : {e}")
            self._view.quit()
            return

        # Au-delà, on quitte sans attendre la confirmation de l'éditeur
        close_deadline = time.time() + CLOSE_EDITOR_TIMEOUT_S

        # Sondage par after() et non Event.wait : on est sur le thread de l'interface, qu'il ne faut pas bloquer
        def wait_for_close() -> None:
            if not self._editor_state.is_open:
                _logger.info("✅ Éditeur fermé")
                self._view.quit()
            elif time.time() >= close_deadline:
                _logger.info("⚠️ L'éditeur n'a pas confirmé sa fermeture : fermeture de l'application quand même")
                self._view.quit()
            else:
                self._view.after(100, wait_for_close)

        self._view.after(100, wait_for_close)

    def on_closing(self) -> None:
        """
        Fermeture de la fenêtre du panneau (X ou bouton Quitter).
        Si l'éditeur est ouvert, demande confirmation puis le ferme avant de quitter.
        """
        if self._closing:
            return  # Fermeture de l'éditeur déjà demandée, en attente de sa confirmation

        if self._editor_state.is_open:
            result = self._view.ask_yes_no(
                "PromptoDYS - Éditeur ouvert",
                "L'éditeur est ouvert.\n\n"
                "Fermer l'application fermera aussi l'éditeur.\n"
                "Pensez à sauvegarder votre document.\n\n"
                "Voulez-vous continuer ?",
            )
            if not result:
                _logger.info("⚠️ Fermeture annulée")
                return
            self._closing = True
            self._close_editor_then_quit()
            return

        # Pas d'éditeur ouvert, fermeture immédiate
        self._view.quit()
