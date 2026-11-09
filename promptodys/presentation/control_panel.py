"""Panneau de contrôle Tkinter (thème Sun Valley) : la fenêtre, ses boutons, sa barre de statut et sa console.

- ControlPanel : la vue Tk ; la logique (boutons, signaux de React, threads, état) est dans PanelController
  (panel_controller.py), qui pilote la fenêtre par les méthodes de PanelView ;
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
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk

import sv_ttk  # Thème Sun Valley (Windows 11 look)

from promptodys.domain import ports
from promptodys.presentation.panel_controller import EditorWindow, PanelController

_logger = logging.getLogger(__name__)


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

    C'est la vue : les boutons et les signaux de React sont transmis à son PanelController, qui la pilote
    en retour par les méthodes de PanelView (show_status, set_processing, dialogues, after, quit...).

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
        self._reports_dir = reports_dir
        self._icon_path = icon_path

        # Construit par le thread de l'interface, comme le panneau : seul autorisé à modifier son état
        self._controller = PanelController(
            view=self,
            editor=editor,
            store=store,
            editor_window=editor_window,
            process_note=process_note,
            documents_dir=documents_dir,
        )

        _logger.info("🖥️ Démarrage du panneau de contrôle GUI...")
        self._build()

    # --- Événements de React (appelés depuis un thread d'Eel), transmis au contrôleur ---

    def on_editor_open(self) -> None:
        """React signale que l'éditeur est prêt"""
        self._controller.on_editor_open()

    def on_editor_close(self) -> None:
        """React signale la fermeture de l'éditeur"""
        self._controller.on_editor_close()

    # --- PanelView : ce que le contrôleur demande à la fenêtre ---

    def show_status(self, text: str) -> None:
        self._status_label.config(text=text)

    def set_processing(self, running: bool) -> None:
        if running:
            self._btn_ai.configure(text="⛔ Abandonner le traitement")
        else:
            self._btn_ai.configure(text="🤖 Traiter la prise de note", state="normal")

    def clear_console(self) -> None:
        # Par la même file que les logs (root.after) : les messages déjà en attente s'affichent avant l'effacement
        self._append_to_console("", clear=True)

    def refresh(self) -> None:
        self._root.update()

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def show_warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message, icon="warning")

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message, icon="warning")

    def ask_open_path(self, initial_dir: str) -> str:
        return filedialog.askopenfilename(
            title="Ouvrir un document PromptoDYS",
            initialdir=initial_dir,
            filetypes=[
                ("Documents Markdown", "*.md"),
                ("Tous les fichiers", "*.*"),
            ],
        )

    def ask_save_path(self, initial_dir: str, initial_name: str) -> str:
        return filedialog.asksaveasfilename(
            title="Enregistrer le document PromptoDYS...",
            initialdir=initial_dir,
            initialfile=initial_name,
            defaultextension="",
            filetypes=[("Tous les fichiers", "*.*")],
        )

    def after(self, delay_ms: int, fn: Callable[[], object]) -> None:
        self._root.after(delay_ms, fn)

    def quit(self) -> None:
        """Ferme le panneau de contrôle et termine le processus"""
        _logger.info("👋 Fermeture de l'application...")
        self._root.destroy()
        os._exit(0)  # Force la fermeture complète

    # --- Console ---

    def _append_to_console(self, text: str, clear: bool = False) -> None:
        """Met à jour la zone de texte des logs, depuis n'importe quel thread"""

        def _update() -> None:
            self._console.configure(state="normal")
            if clear:
                self._console.delete("1.0", "end")
            self._console.insert("end", text)
            self._console.see("end")  # Auto-scroll
            self._console.configure(state="disabled")

        self.after(0, _update)

    def _write_to_console(self, msg: str) -> None:
        """Reçoit ce qui est écrit sur stdout et stderr (voir RedirectText)"""
        # Filtrer les messages vides
        if msg and msg.strip():
            self._append_to_console(msg)
        elif msg == "\n":
            self._append_to_console("\n")

    # --- Bouton sans état ---

    def _open_reports_folder(self) -> None:
        """Ouvre le dossier des rapports PDF dans l'explorateur Windows"""
        _logger.info("📂 Action: Ouverture du dossier reports...")
        reports_path = self._reports_dir

        # Créer le dossier s'il n'existe pas
        os.makedirs(reports_path, exist_ok=True)

        # Ouvrir le dossier dans l'explorateur Windows
        try:
            subprocess.Popen(f'explorer "{reports_path}"')
            self.show_status("📂 Dossier reports ouvert")
        except Exception as e:
            self.show_status(f"❌ Erreur ouverture: {str(e)[:20]}")
            _logger.info(f"❌ Erreur ouverture dossier: {e}")

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
        root.protocol("WM_DELETE_WINDOW", self._controller.on_closing)

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
            command=self._controller.open_editor,
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
            command=self._controller.save_document,
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
            command=self._controller.open_document,
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
            command=self._controller.toggle_processing,
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
            command=self._controller.on_closing,
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
