"""Panneau de contrôle Tkinter (thème Sun Valley) : ouvrir l'éditeur, sauvegarder et ouvrir un document,
lancer ou abandonner le traitement IA, voir les rapports, quitter.

- ControlPanel : la fenêtre et ses boutons ; l'état de l'éditeur est un EditorState (editor_state.py) ;
- EditorWindow : ce que le panneau attend de la fenêtre de l'éditeur (EelWindow dans l'infrastructure) ;
- RedirectText : affiche stdout et stderr dans la console du panneau.

Le panneau reçoit toutes ses dépendances de main() : il n'importe ni l'infrastructure, ni eel, google
ou reportlab (contrat import-linter).
"""

import contextlib
import logging
import os
import subprocess  # Pour ouvrir le dossier reports
import sys
import threading
import time
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from typing import Protocol

import sv_ttk  # Thème Sun Valley (Windows 11 look)

from promptodys.domain import documents, ports
from promptodys.presentation.editor_state import EditorState

_logger = logging.getLogger(__name__)

# Délai maximum d'attente de la fermeture de l'éditeur avant de quitter quand même
CLOSE_EDITOR_TIMEOUT_S = 3
# Délai maximum d'attente du signal de React (on_editor_open) avant d'ouvrir un document
EDITOR_READY_TIMEOUT_S = 30
# Après le signal de React, laisse l'éditeur finir d'initialiser ses composants
REACT_SETTLE_DELAY_S = 1.5


# Classe pour rediriger stdout vers la GUI
# Classe pour rediriger stdout/stderr vers la GUI tout en gardant la console
class RedirectText:
    def __init__(self, text_widget_updater, is_stderr=False):
        self.updater = text_widget_updater
        self.is_stderr = is_stderr
        # On garde une référence vers le VRAI stdout/stderr d'origine
        if is_stderr:
            self.terminal = sys.__stderr__
        else:
            self.terminal = sys.__stdout__

    def write(self, message):
        # Écrire dans la console réelle (si disponible)
        if self.terminal:
            with contextlib.suppress(Exception):
                self.terminal.write(message)
                self.terminal.flush()

        # Mettre à jour la GUI (éviter de planter si la GUI est fermée)
        with contextlib.suppress(Exception):
            self.updater(message)

    def flush(self):
        if self.terminal:
            with contextlib.suppress(Exception):
                self.terminal.flush()


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


def _on_button_enter(btn: tk.Button) -> None:
    """Effet au survol : bordure bleue, fond bleu clair, texte bleu"""
    btn.config(
        bg="#E3F2FD",  # Fond bleu clair
        fg="#0078D4",  # Texte bleu
        highlightbackground="#0078D4",  # Bordure bleue (épaisseur inchangée : la mise en page ne bouge pas)
    )


def _on_button_leave(btn: tk.Button) -> None:
    """Retour à l'état normal"""
    btn.config(
        bg="#FFFFFF",  # Fond blanc
        fg="#1F1F1F",  # Texte noir
        highlightbackground="#333333",  # Bordure sombre
    )


def _on_button_press(btn: tk.Button) -> None:
    """Effet au clic : enfoncement visuel"""
    btn.config(relief="sunken")


def _on_button_release(btn: tk.Button) -> None:
    """Retour au relief normal après clic"""
    btn.config(relief="raised")


class ControlPanel:
    """
    Panneau de contrôle avec Tkinter + sv_ttk (thème Windows 11) : ouvrir l'éditeur, sauvegarder
    et ouvrir un document, lancer ou abandonner le traitement IA, voir les rapports, quitter.

    L'état de l'éditeur (_editor_state, voir EditorState) est géré exclusivement par les événements
    de React et par le retour de editor_window.start() :
    - _open_editor()    : lancement demandé (start_requested) ;
    - on_editor_open()  : React notifie l'ouverture (opened), fin du lancement ;
    - on_editor_close() : React notifie la fermeture (closed) ;
    - _launch_editor()  : port pris, editor_window.start() qui retourne ou qui lève (closed).

    __init__ construit la fenêtre (cachée), run() l'affiche et lance la boucle principale.
    """

    def __init__(
        self,
        editor: ports.Editor,
        store: ports.DocumentStore,
        editor_window: EditorWindow,
        process_note: Callable[[threading.Event], bool],
        documents_dir: str,
        reports_dir: str,
        icon_path: str,
    ) -> None:
        self._editor = editor
        self._store = store
        self._editor_window = editor_window
        self._process_note = process_note
        self._documents_dir = documents_dir
        self._reports_dir = reports_dir
        self._icon_path = icon_path

        # --- État de l'éditeur (modifié aussi par les événements de React, depuis un thread d'Eel) ---
        self._editor_state = EditorState()
        # Fermeture de l'éditeur demandée, en attente de sa confirmation : ignore un second clic sur Quitter
        self._closing = False

        # --- État du traitement IA ---
        # Jeton d'annulation du traitement IA en cours, None si aucun traitement en cours
        self._cancel_event: threading.Event | None = None

        _logger.info("🖥️ Démarrage du panneau de contrôle GUI...")
        self._build()

    # --- Accès au thread de l'interface ---

    def _in_ui_thread(self, fn: Callable[[], object]) -> None:
        """Fait exécuter fn par le thread de l'interface : seul passage autorisé depuis les autres threads
        (Tkinter n'est pas thread-safe). La file d'attente prévue par R7 ne changera que cette méthode."""
        self._root.after(0, fn)

    def _append_to_console(self, text: str, clear: bool = False) -> None:
        """Met à jour la zone de texte des logs, depuis n'importe quel thread"""

        def _update() -> None:
            self._console.configure(state="normal")
            if clear:
                self._console.delete("1.0", "end")
            self._console.insert("end", text)
            self._console.see("end")  # Auto-scroll
            self._console.configure(state="disabled")

        self._in_ui_thread(_update)

    def _write_to_console(self, msg: str) -> None:
        """Reçoit ce qui est écrit sur stdout et stderr (voir RedirectText)"""
        # Filtrer les messages vides
        if msg and msg.strip():
            self._append_to_console(msg)
        elif msg == "\n":
            self._append_to_console("\n")

    # --- Événements de React (appelés depuis un thread d'Eel) ---

    def on_editor_open(self) -> None:
        """React signale que l'éditeur est prêt"""
        self._editor_state.opened()
        self._in_ui_thread(lambda: self._status_label.config(text="✅ Éditeur ouvert"))

    def on_editor_close(self) -> None:
        """React signale la fermeture de l'éditeur"""
        self._editor_state.closed()
        self._in_ui_thread(lambda: self._status_label.config(text="🔴 Éditeur fermé"))

    # --- Boutons ---

    def _open_editor(self) -> None:
        """Lance l'éditeur dans un thread séparé"""
        if self._editor_state.is_open:
            _logger.info("📝 L'éditeur est déjà ouvert")
            self._status_label.config(text="✅ L'éditeur est déjà ouvert")
            return

        if self._editor_state.is_starting:
            _logger.info("📝 L'éditeur est déjà en cours d'ouverture")
            self._status_label.config(text="⏳ Ouverture de l'éditeur en cours, veuillez patienter")
            return

        # Dès le clic : un second clic pendant l'attente du port ou de Chrome ne relance rien
        self._editor_state.start_requested()
        _logger.info("📝 Action: Lancement de l'éditeur...")
        self._status_label.config(text="⏳ Ouverture de l'éditeur en cours, veuillez patienter")
        self._root.update()

        # Lancer dans un thread pour ne pas bloquer la GUI
        thread = threading.Thread(target=self._launch_editor, daemon=True)
        thread.start()
        # « ✅ Éditeur ouvert » est affiché par on_editor_open(), quand React signale que l'éditeur est prêt

    def _show_launch_failure(self, status: str, message: str) -> None:
        """Échec du lancement : statut et popup, affichés par le thread de l'interface"""

        def _show() -> None:
            self._status_label.config(text=status)
            messagebox.showerror("PromptoDYS - Éditeur non ouvert", message)

        self._in_ui_thread(_show)

    def _launch_editor(self) -> None:
        """Ouvre l'éditeur (thread dédié) et attend sa fermeture"""
        port = self._editor_window.port
        # Vérifier le port avant d'ouvrir Chrome : s'il est pris, Chrome afficherait
        # la page de l'autre programme. On n'ouvre alors aucune fenêtre.
        if not self._editor_window.wait_for_free_port():
            _logger.info(f"❌ Le port {port} est utilisé par un autre programme : éditeur non ouvert")
            self._editor_state.closed()
            self._show_launch_failure(
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
            self._editor_state.closed()
            self._show_launch_failure(
                "❌ Échec de l'ouverture de l'éditeur (voir les logs)",
                "L'éditeur n'a pas pu s'ouvrir.\n\n"
                "Vérifiez que Google Chrome est installé,\n"
                "puis réessayez.\n\n"
                "Le détail de l'erreur est dans la console.",
            )
            return

        # Quand l'éditeur se ferme, on met à jour le statut. L'état est remis à « fermé » même si
        # React n'a jamais signalé l'ouverture, ou n'a pas signalé la fermeture (plantage de Chrome)
        self._in_ui_thread(lambda: self._status_label.config(text="🔴 Éditeur fermé"))
        self._editor_state.closed()

    def _save_document(self) -> None:
        """Sauvegarde le document — toujours en mode "Enregistrer sous" (dialogue à chaque fois).
        Si un document est déjà ouvert, le dialogue pré-remplit le nom et le dossier courant."""
        if not self._editor_state.is_open:
            messagebox.showwarning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\nVeuillez d'abord ouvrir l'éditeur\navant de sauvegarder.",
                icon="warning",
            )
            self._status_label.config(text="⚠️ Éditeur non ouvert")
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
            selected = filedialog.asksaveasfilename(
                title="Enregistrer le document PromptoDYS...",
                initialdir=initial_dir,
                initialfile=initial_name,
                defaultextension="",
                filetypes=[("Tous les fichiers", "*.*")],
            )
            if not selected:
                _logger.info("💾 Sauvegarde annulée par l'utilisateur")
                return

            save_dir, doc_name = documents.prepare_save_path(selected)
            if doc_name:
                break

            _logger.info(f"⚠️ Nom de document invalide: '{os.path.basename(selected)}'")
            messagebox.showwarning(
                "PromptoDYS - Nom invalide",
                "Le nom du document est vide\n"
                "ou commence par un point.\n\n"
                "Veuillez saisir un nom\n"
                "(lettres ou chiffres).",
                icon="warning",
            )
            initial_dir = os.path.dirname(selected)
            initial_name = "nouveau_document"

        self._status_label.config(text="⏳ Sauvegarde en cours...")
        self._root.update()

        def run_save() -> None:
            _logger.info(f"🔍 DEBUG run_save: doc_name='{doc_name}', save_dir='{save_dir}'")
            result = documents.save_document(self._editor, self._store, save_dir, doc_name)
            if result:
                self._editor_state.document_path = result
                self._in_ui_thread(lambda: self._status_label.config(text=f"✅ '{doc_name}' sauvegardé !"))
                _logger.info(f"✅ Document sauvegardé dans: {result}")
            else:
                self._in_ui_thread(lambda: self._status_label.config(text="❌ Erreur de sauvegarde"))

        thread = threading.Thread(target=run_save, daemon=True)
        thread.start()

    def _open_document(self) -> None:
        """Ouvre un document complet (texte + images) via filedialog — accepte dossier ou fichier .md
        Si l'éditeur n'est pas lancé, il est ouvert automatiquement avant le chargement."""
        # 1. Choisir le fichier AVANT de lancer l'éditeur (le filedialog est indépendant)
        selected_path = filedialog.askopenfilename(
            title="Ouvrir un document PromptoDYS",
            initialdir=self._documents_dir,
            filetypes=[
                ("Documents Markdown", "*.md"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not selected_path:
            _logger.info("📂 Ouverture annulée par l'utilisateur")
            return

        # 2. Si l'éditeur n'est pas ouvert, le lancer automatiquement
        need_wait = not self._editor_state.is_open
        if need_wait:
            _logger.info("📂 Éditeur non ouvert → lancement automatique avant ouverture du document...")
            self._status_label.config(text="⏳ Lancement de l'éditeur...")
            self._root.update()
            self._open_editor()

        self._status_label.config(text="⏳ Ouverture en cours...")
        self._root.update()

        # 3. Attendre que l'éditeur soit prêt, puis charger le document
        def run_load() -> None:
            if need_wait:
                # Attendre le signal de React (on_editor_open)
                _logger.info("⏳ Attente du signal React on_editor_open()...")
                if not self._editor_state.wait_until_open(EDITOR_READY_TIMEOUT_S):
                    _logger.info(
                        f"❌ Timeout: React n'a pas signalé on_editor_open() dans les {EDITOR_READY_TIMEOUT_S} secondes"
                    )
                    self._in_ui_thread(lambda: self._status_label.config(text="❌ Éditeur non prêt (timeout)"))
                    return

                # Petit délai pour laisser React finir l'initialisation complète des composants
                time.sleep(REACT_SETTLE_DELAY_S)

            _logger.info("✅ Éditeur prêt, chargement du document...")

            result = documents.open_document(self._editor, self._store, selected_path)
            if result:
                # Mémoriser le dossier du document ouvert (comme Arduino retient le sketch ouvert)
                self._editor_state.document_path = result
                doc_name = os.path.basename(result)
                _logger.info(f"📌 Document courant: {result}")
                self._in_ui_thread(lambda: self._status_label.config(text=f"✅ '{doc_name}' ouvert !"))
            else:
                self._in_ui_thread(lambda: self._status_label.config(text="❌ Erreur d'ouverture"))

        thread = threading.Thread(target=run_load, daemon=True)
        thread.start()

    def _toggle_processing(self) -> None:
        """Lance le traitement IA Gemini ou demande l'abandon"""
        # SI DÉJÀ EN COURS -> ABANDON IMMÉDIAT
        # Le thread de traitement ne peut pas être interrompu s'il attend Gemini :
        # on déclenche son jeton et on libère l'interface sans l'attendre.
        # S'il se réveille plus tard, il voit son jeton déclenché et s'arrête sans rien écrire.
        if self._cancel_event is not None:
            _logger.info("\n🚫 ABANDON: Traitement IA arrêté par l'utilisateur.")
            self._cancel_event.set()
            self._cancel_event = None
            self._btn_ai.configure(text="🤖 Traiter la prise de note", state="normal")
            self._status_label.config(text="🚫 Traitement annulé")
            return

        # VÉRIFICATION 1: Connexion internet - SUPPRIMÉE
        _logger.info("\n🔍 VÉRIFICATION PRÉ-TRAITEMENT IA...")

        # VÉRIFICATION 2: Éditeur ouvert
        if not self._editor_state.is_open:
            _logger.info("⚠️ L'éditeur n'est pas ouvert !")
            messagebox.showwarning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\nVeuillez d'abord ouvrir l'éditeur\navant de lancer le traitement IA.",
                icon="warning",
            )
            self._status_label.config(text="⚠️ Éditeur non ouvert")
            return

        _logger.info("🤖 Action: Lancement du traitement IA...")
        self._status_label.config(text="⏳ Traitement IA en cours...")

        # Nouveau jeton d'annulation, propre à ce traitement. Il est enregistré AVANT root.update()
        # et le thread, pour qu'un second clic soit traité comme une demande d'abandon
        cancel = threading.Event()
        self._cancel_event = cancel

        # Mise à jour du bouton en mode "Abandon"
        self._btn_ai.configure(text="⛔ Abandonner le traitement")
        self._root.update()

        # Nouveau traitement : console vidée AVANT le premier log du traitement. L'effacement passe
        # par la même file que l'affichage (root.after) : les logs du thread s'afficheront après lui
        self._append_to_console("", clear=True)

        def finish(success: bool) -> None:
            """Fin du traitement, exécutée sur le thread principal (via root.after)"""
            # Traitement abandonné (et peut-être remplacé par un autre) : l'interface est déjà à jour
            if self._cancel_event is not cancel:
                return
            self._cancel_event = None
            _logger.info("🔄 FIN: Réinitialisation du bouton de contrôle")
            self._btn_ai.configure(text="🤖 Traiter la prise de note", state="normal")
            if success:
                self._status_label.config(text="✅ Traitement IA terminé !")
            else:
                self._status_label.config(text="❌ Échec du traitement IA (voir les logs)")

        # Lancer le traitement dans un thread pour ne pas bloquer la GUI
        # Ce thread ne modifie aucune variable d'état : il confie la fin au thread principal
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

    def _open_reports_folder(self) -> None:
        """Ouvre le dossier des rapports PDF dans l'explorateur Windows"""
        _logger.info("📂 Action: Ouverture du dossier reports...")
        reports_path = self._reports_dir

        # Créer le dossier s'il n'existe pas
        os.makedirs(reports_path, exist_ok=True)

        # Ouvrir le dossier dans l'explorateur Windows
        try:
            subprocess.Popen(f'explorer "{reports_path}"')
            self._status_label.config(text="📂 Dossier reports ouvert")
        except Exception as e:
            self._status_label.config(text=f"❌ Erreur ouverture: {str(e)[:20]}")
            _logger.info(f"❌ Erreur ouverture dossier: {e}")

    # --- Fermeture ---

    def _quit(self) -> None:
        """Ferme le panneau de contrôle et termine le processus"""
        _logger.info("👋 Fermeture de l'application...")
        self._root.destroy()
        os._exit(0)  # Force la fermeture complète

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
            self._quit()
            return

        # Au-delà, on quitte sans attendre la confirmation de l'éditeur
        close_deadline = time.time() + CLOSE_EDITOR_TIMEOUT_S

        # Sondage par root.after et non Event.wait : on est sur le thread de l'interface, qu'il ne faut pas bloquer
        def wait_for_close() -> None:
            if not self._editor_state.is_open:
                _logger.info("✅ Éditeur fermé")
                self._quit()
            elif time.time() >= close_deadline:
                _logger.info("⚠️ L'éditeur n'a pas confirmé sa fermeture : fermeture de l'application quand même")
                self._quit()
            else:
                self._root.after(100, wait_for_close)

        self._root.after(100, wait_for_close)

    def on_closing(self) -> None:
        """
        Intercepte la fermeture de la fenêtre GUI (X ou bouton Quitter).
        Si l'éditeur est ouvert, demande confirmation puis le ferme avant de quitter.
        """
        if self._closing:
            return  # Fermeture de l'éditeur déjà demandée, en attente de sa confirmation

        if self._editor_state.is_open:
            result = messagebox.askyesno(
                "PromptoDYS - Éditeur ouvert",
                "L'éditeur est ouvert.\n\n"
                "Fermer l'application fermera aussi l'éditeur.\n"
                "Pensez à sauvegarder votre document.\n\n"
                "Voulez-vous continuer ?",
                icon="warning",
            )
            if not result:
                _logger.info("⚠️ Fermeture annulée")
                return
            self._closing = True
            self._close_editor_then_quit()
            return

        # Pas d'éditeur ouvert, fermeture immédiate
        self._quit()

    # --- Défilement de la fenêtre ---

    def _content_overflows(self) -> bool:
        """Vrai si le contenu est plus haut que la zone visible"""
        return self._main_frame.winfo_reqheight() > self._canvas.winfo_height()

    def _update_scrolling(self, event: object = None) -> None:
        """Met à jour la zone défilable et affiche la barre seulement si nécessaire"""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        # La barre ne change que la largeur du canvas, pas sa hauteur : pas d'oscillation
        if self._content_overflows():
            if not self._canvas_scrollbar.winfo_manager():  # Pas encore packée
                self._canvas_scrollbar.pack(side="right", fill="y", before=self._canvas)
        elif self._canvas_scrollbar.winfo_manager():
            self._canvas_scrollbar.pack_forget()
            self._canvas.yview_moveto(0)  # Revenir en haut quand tout tient

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Cale la largeur du contenu sur celle du canvas"""
        self._canvas.itemconfigure(self._main_frame_id, width=event.width)
        self._update_scrolling()

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        """Fait défiler la fenêtre, sauf au-dessus de la console (qui a son propre défilement)"""
        try:
            widget = self._root.winfo_containing(event.x_root, event.y_root)
        except KeyError:
            return  # Widget interne à Tk, inconnu de tkinter (ex. : dialogue)
        if widget is None or widget is self._console or widget.winfo_toplevel() is not self._root:
            return
        if not self._content_overflows():
            return  # Tout tient : rien à faire défiler
        if sys.platform == "darwin":
            unites = -event.delta  # macOS : delta petit (±1, ±2...)
        else:
            unites = -3 * int(event.delta / 120)  # Windows : ±120 par cran, 3 unités par cran
            if unites == 0:
                unites = -1 if event.delta > 0 else 1  # Pavé tactile : delta inférieur à 120
        self._canvas.yview_scroll(unites, "units")

    # --- Construction de la fenêtre ---

    def _build(self) -> None:
        """Crée la fenêtre principale et ses widgets, cachée jusqu'à run()"""
        # --- Création de la fenêtre principale ---
        root = tk.Tk()
        root.withdraw()  # Cachée jusqu'à run(), une fois sa taille calculée
        self._root = root
        root.title("PromptoDYS - Panneau de Contrôle")
        root.configure(bg="#F3F3F3")  # Fond gris
        root.resizable(True, True)  # Fenêtre redimensionnable

        # Intercepter la fermeture de la fenêtre (X rouge)
        root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- Icône de la fenêtre ---
        try:
            icon_image = tk.PhotoImage(file=self._icon_path)
            root.iconphoto(True, icon_image)
            _logger.info(f"✅ Icône chargée: {self._icon_path}")
        except Exception as e:
            _logger.info(f"⚠️ Icône non chargée: {e}")

        # Appliquer le thème Sun Valley (mode clair)
        sv_ttk.set_theme("light")  # Thème clair Windows 11

        # --- Créer un style pour le fond gris ---
        style = ttk.Style()
        style.configure("Gray.TFrame", background="#F3F3F3")

        # sv_ttk applique sa palette (tk_setPalette) au prochain tour de boucle, sur tous les widgets tk,
        # après set_theme() et après chaque style.configure(). Sans cet update, les couleurs choisies
        # plus bas (bordure sombre des boutons, fonds) seraient écrasées par le gris clair du thème.
        # Aucun style ne doit être configuré après cette ligne. La fenêtre est encore cachée.
        root.update()

        # --- Zone défilante (si la fenêtre est plus petite que son contenu) ---
        canvas = tk.Canvas(root, bg="#F3F3F3", highlightthickness=0, bd=0, yscrollincrement=20)  # Défilement : 20px
        self._canvas = canvas
        canvas_scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        self._canvas_scrollbar = canvas_scrollbar
        canvas.configure(yscrollcommand=canvas_scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        # La barre n'est packée que si le contenu dépasse (voir _update_scrolling)

        # --- Frame principal avec padding (placé dans le canvas) ---
        main_frame = ttk.Frame(canvas, padding=(20, 20, 20, 20), style="Gray.TFrame")  # Fond gris
        self._main_frame = main_frame
        self._main_frame_id = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        main_frame.bind("<Configure>", self._update_scrolling)
        canvas.bind("<Configure>", self._on_canvas_configure)

        # --- Titre avec logo ---
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(pady=(0, 5))  # Réduit de 10 à 5

        # Charger le logo prompto pour le titre (redimensionné)
        try:
            logo_image_title = tk.PhotoImage(file=self._icon_path)
            # Redimensionner le logo (subsample = diviser par n)
            logo_image_title = logo_image_title.subsample(5, 5)  # Réduit encore plus (de 4 à 5)
            self._logo = logo_image_title  # Garder une référence, sinon Tk efface l'image
            logo_label = ttk.Label(title_frame, image=logo_image_title)
            logo_label.pack(side="left", padx=(0, 15))
            _logger.info("✅ Logo titre chargé")
        except Exception as e:
            _logger.info(f"⚠️ Logo titre non chargé: {e}")

        title_label = ttk.Label(
            title_frame,
            text="PromptoDYS",
            font=("Segoe UI", 24, "bold"),  # Réduit de 32 à 24
        )
        title_label.pack(side="left")

        # --- Boutons (tk.Button classiques pour bordures épaisses) ---
        # Bouton 1: Ouvrir l'éditeur
        btn1 = tk.Button(
            main_frame,
            text="📝 Ouvrir l'Éditeur",
            command=self._open_editor,
            font=("Segoe UI", 16, "bold"),
            bg="#FFFFFF",  # Fond blanc
            fg="#1F1F1F",  # Texte noir
            relief="raised",
            bd=12,  # Bordure très épaisse
            highlightbackground="#333333",  # Bordure sombre
            highlightthickness=12,  # Épaisseur bordure highlight
            padx=20,
            pady=15,
            cursor="hand2",
        )
        btn1.pack(pady=8, fill="x", padx=20)
        # Lier les événements de survol
        btn1.bind("<Enter>", lambda e: _on_button_enter(btn1))
        btn1.bind("<Leave>", lambda e: _on_button_leave(btn1))
        btn1.bind("<ButtonPress-1>", lambda e: _on_button_press(btn1))
        btn1.bind("<ButtonRelease-1>", lambda e: _on_button_release(btn1))

        # --- Section Document : Sauvegarder / Ouvrir (côte à côte dans un LabelFrame) ---
        doc_frame = ttk.LabelFrame(main_frame, text="📄 Document", padding=(10, 5))
        doc_frame.pack(fill="x", padx=20, pady=8)

        # Configurer 2 colonnes de poids égal pour répartir l'espace
        doc_frame.columnconfigure(0, weight=1)
        doc_frame.columnconfigure(1, weight=1)

        # Bouton Sauvegarder (colonne gauche)
        btn_save = tk.Button(
            doc_frame,
            text="💾 Sauvegarder",
            command=self._save_document,
            font=("Segoe UI", 13, "bold"),
            bg="#FFFFFF",
            fg="#1F1F1F",
            relief="raised",
            bd=8,
            highlightbackground="#333333",
            highlightthickness=8,
            padx=10,
            pady=10,
            cursor="hand2",
        )
        btn_save.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=5)
        btn_save.bind("<Enter>", lambda e: _on_button_enter(btn_save))
        btn_save.bind("<Leave>", lambda e: _on_button_leave(btn_save))
        btn_save.bind("<ButtonPress-1>", lambda e: _on_button_press(btn_save))
        btn_save.bind("<ButtonRelease-1>", lambda e: _on_button_release(btn_save))

        # Bouton Ouvrir (colonne droite)
        btn_open = tk.Button(
            doc_frame,
            text="📂 Ouvrir",
            command=self._open_document,
            font=("Segoe UI", 13, "bold"),
            bg="#FFFFFF",
            fg="#1F1F1F",
            relief="raised",
            bd=8,
            highlightbackground="#333333",
            highlightthickness=8,
            padx=10,
            pady=10,
            cursor="hand2",
        )
        btn_open.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=5)
        btn_open.bind("<Enter>", lambda e: _on_button_enter(btn_open))
        btn_open.bind("<Leave>", lambda e: _on_button_leave(btn_open))
        btn_open.bind("<ButtonPress-1>", lambda e: _on_button_press(btn_open))
        btn_open.bind("<ButtonRelease-1>", lambda e: _on_button_release(btn_open))

        # Bouton 2: Traitement IA
        btn_ai = tk.Button(
            main_frame,
            text="🤖 Traiter la prise de note",
            command=self._toggle_processing,
            font=("Segoe UI", 16, "bold"),
            bg="#FFFFFF",
            fg="#1F1F1F",
            relief="raised",
            bd=12,
            highlightbackground="#333333",
            highlightthickness=12,
            padx=20,
            pady=15,
            cursor="hand2",
        )
        self._btn_ai = btn_ai
        btn_ai.pack(pady=8, fill="x", padx=20)
        btn_ai.bind("<Enter>", lambda e: _on_button_enter(btn_ai))
        btn_ai.bind("<Leave>", lambda e: _on_button_leave(btn_ai))
        btn_ai.bind("<ButtonPress-1>", lambda e: _on_button_press(btn_ai))
        btn_ai.bind("<ButtonRelease-1>", lambda e: _on_button_release(btn_ai))

        # Bouton 3: Ouvrir rapports PDF
        btn3 = tk.Button(
            main_frame,
            text="📂 Voir les rapports PDF",
            command=self._open_reports_folder,
            font=("Segoe UI", 16, "bold"),
            bg="#FFFFFF",
            fg="#1F1F1F",
            relief="raised",
            bd=12,
            highlightbackground="#333333",
            highlightthickness=12,
            padx=20,
            pady=15,
            cursor="hand2",
        )
        btn3.pack(pady=8, fill="x", padx=20)
        btn3.bind("<Enter>", lambda e: _on_button_enter(btn3))
        btn3.bind("<Leave>", lambda e: _on_button_leave(btn3))
        btn3.bind("<ButtonPress-1>", lambda e: _on_button_press(btn3))
        btn3.bind("<ButtonRelease-1>", lambda e: _on_button_release(btn3))

        # --- Séparateur ---
        separator = ttk.Separator(main_frame, orient="horizontal")
        separator.pack(fill="x", pady=10)  # Réduit de 20 à 10

        # --- Barre de statut ---
        status_label = ttk.Label(
            main_frame,
            text="🟢 Prêt",
            font=("Segoe UI", 14),  # Réduit de 18 à 14
        )
        status_label.pack(pady=5)  # Réduit de 10 à 5
        self._status_label = status_label

        # --- Zone de texte pour le streaming IA ---
        # Renommé pour refléter qu'il contient tous les logs
        streaming_frame = ttk.LabelFrame(main_frame, text="📝 Console / Logs", padding=10)
        streaming_frame.pack(fill="both", expand=False, pady=10)

        # Créer une zone de texte avec scrollbar
        console = tk.Text(
            streaming_frame,
            height=4,  # Exactement 4 lignes complètes
            width=60,
            font=("Consolas", 10),  # Police légèrement plus petite pour logs
            wrap="word",
            state="disabled",  # Lecture seule
            bg="#f8f8f8",
            fg="#333333",
        )
        self._console = console
        scrollbar = ttk.Scrollbar(streaming_frame, orient="vertical", command=console.yview)
        console.configure(yscrollcommand=scrollbar.set)

        console.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Bouton Quitter (plus petit, en bas) ---
        btn_quit = tk.Button(
            main_frame,
            text="❌ Quitter",
            command=self.on_closing,
            font=("Segoe UI", 14),
            bg="#F5F5F5",
            fg="#666666",
            relief="raised",
            bd=8,
            highlightbackground="#999999",
            highlightthickness=8,
            padx=15,
            pady=10,
            cursor="hand2",
        )
        btn_quit.pack(pady=0)  # Aucune marge
        # Effets de survol spécifiques pour le bouton Quitter
        btn_quit.bind("<Enter>", lambda e: btn_quit.config(bg="#FFE6E6", fg="#CC0000", highlightbackground="#CC0000"))
        btn_quit.bind("<Leave>", lambda e: btn_quit.config(bg="#F5F5F5", fg="#666666", highlightbackground="#999999"))

        # --- Molette : défilement de la fenêtre ---
        root.bind_all("<MouseWheel>", self._on_mouse_wheel)

        # --- Taille de la fenêtre calculée depuis le contenu ---
        root.update_idletasks()  # Calculer la taille demandée par chaque widget
        hauteur_ideale = main_frame.winfo_reqheight()  # Tout le contenu, padding et bouton Quitter compris
        hauteur_disponible = int(root.winfo_screenheight() * 0.9)  # 90 % de l'écran
        hauteur = min(hauteur_ideale, hauteur_disponible)
        largeur_ideale = main_frame.winfo_reqwidth()  # Largeur sous laquelle le contenu serait écrasé
        if hauteur_ideale > hauteur_disponible:
            largeur_ideale += canvas_scrollbar.winfo_reqwidth()  # La barre de défilement prend sa place à droite
        root.geometry(f"{largeur_ideale}x{hauteur}")
        root.minsize(largeur_ideale, hauteur)  # Taille minimale : rien de caché ni d'écrasé

    def run(self) -> None:
        """Redirige stdout et stderr vers la console du panneau, affiche la fenêtre
        et lance la boucle principale (bloquant)"""
        # --- Redirection de stdout ET stderr vers la GUI ---
        # Rediriger stdout (prints normaux)
        sys.stdout = RedirectText(self._write_to_console, is_stderr=False)
        # Rediriger stderr (erreurs, exceptions)
        sys.stderr = RedirectText(self._write_to_console, is_stderr=True)

        print("✅ Console et Erreurs redirigées vers la GUI")

        self._root.deiconify()  # Afficher la fenêtre à sa taille définitive

        # --- Lancer la boucle principale ---
        print("✅ Panneau de contrôle GUI prêt !")
        self._root.mainloop()
