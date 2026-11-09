#!/usr/bin/env python3
"""
Script Python unifié pour l'éditeur Markdown avec intégration Eel + IA Gemini
Combinaison : Interface desktop + Assistant IA pour traitement de texte

GUI de contrôle avec Tkinter + sv_ttk (thème Sun Valley Windows 11)

Installation requise (dépendances déclarées dans pyproject.toml):
uv sync --locked
Usage:
uv run python askGeminiPrompto.py

Fichiers requis:
- GeminiKey.txt (clé API Gemini)
- promptodys.prompt (template de traitement IA)
- build/index.html (interface web)

Fonctionnalités:
- Sauvegarde automatique des rapports en PDF uniquement
- Rendu Markdown professionnel dans les PDF avec reportlab
- Interface console simple et efficace
- Dossier reports/ créé automatiquement
- CAPTURE COMPLÈTE de tous les logs dans les rapports
"""

import contextlib
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

# --- Imports GUI Tkinter + sv_ttk ---
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sv_ttk  # Thème Sun Valley (Windows 11 look)
import subprocess  # Pour ouvrir le dossier reports

# --- Couche domaine (règles pures, voir promptodys/) ---
from promptodys.domain import documents, ports, processing

# --- Couche infrastructure (adaptateurs, configuration) ---
from promptodys.infrastructure import config, disk_document_store, eel_editor, gemini_model, pdf_report

# --- NOUVELLE VARIABLE POUR CAPTURER TOUS LES LOGS ---
logs_complets = []


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


def log_message(message):
    """Log un message dans la console ET le capture pour les rapports"""
    print(message, flush=True)
    # Les prints sont maintenant redirigés vers la GUI via stdout mais on garde l'ajout explicite aux logs complets
    # Capturer aussi dans les logs complets
    logs_complets.append(message)


class LogMessageHandler(logging.Handler):
    """Pont provisoire : renvoie les logs de la couche domaine vers log_message (console, GUI, rapport).
    Sera remplacé par les vrais handlers de logging avec R7."""

    def emit(self, record):
        with contextlib.suppress(Exception):
            log_message(self.format(record))


def configure_logger():
    """Envoie les logs du paquet promptodys vers log_message, message seul (sans niveau ni heure).
    Appelée par main(), jamais à l'import : les tests gardent la configuration de logging par défaut."""
    logger = logging.getLogger("promptodys")
    logger.setLevel(logging.INFO)
    logger.addHandler(LogMessageHandler())
    logger.propagate = False  # pas de second affichage par le logger racine


# Éditeur utilisé par le traitement IA et par le panneau (aucun effet de bord à la construction)
editeur_eel = eel_editor.EelEditor()


# --- Fonctions Gemini ---


def traitement_gemini(annulation):
    """Traitement IA Gemini : client → modèle de prompt → cas d'usage processing.process_note → rapport PDF

    annulation : threading.Event propre à ce traitement, déclenché par le bouton « Abandonner ».
    Un traitement abandonné s'arrête à la sortie du flux, sans rien écrire dans l'éditeur ni le PDF.

    Renvoie True si le traitement est allé jusqu'au bout, False en cas d'échec ou d'abandon.
    """
    # Nouveau traitement : logs du rapport vidés AVANT le premier log
    # (la console, elle, est vidée par le panneau juste avant le lancement du traitement)
    global logs_complets
    logs_complets = []

    log_message("\n🤖 DÉMARRAGE: TRAITEMENT IA GEMINI (ANNULABLE)")
    log_message("=" * 50)

    # 1. Initialiser le client et sa configuration
    log_message("🔑 ÉTAPE 1: Initialisation du client Gemini...")
    client = gemini_model.create_client()
    if not client:
        log_message("❌ ÉCHEC: Impossible d'initialiser Gemini")
        return False
    modele = gemini_model.GeminiModel(client)
    log_message(
        f"✅ SUCCÈS: Client Gemini initialisé (Modèle: {config.GEMINI_MODEL}, "
        f"Thinking level: {config.GEMINI_THINKING_LEVEL.value})"
    )

    # 2. Lire le modèle de prompt
    log_message("\n📋 ÉTAPE 2: Lecture du template promptodys.prompt...")
    prompt_template = config.read_prompt_template()
    if not prompt_template:
        log_message("❌ ÉCHEC: Impossible de lire promptodys.prompt")
        return False
    log_message("✅ SUCCÈS: Template promptodys.prompt chargé")

    # Logs des étapes 1 et 2, complétés par ceux de la préparation (étapes 3 et 4) pour le rapport
    logs_avant_traitement = logs_complets.copy()

    # 3 à 8. Lecture de l'éditeur, prompt, flux IA, extraction, injection, jetons
    resultat = processing.process_note(editeur_eel, modele, prompt_template, annulation, datetime.now().date())
    if resultat.status is not processing.ProcessingStatus.COMPLETED:
        return False

    # 9. Sauvegarde automatique PDF uniquement
    log_message("\n💾 ÉTAPE 9: Sauvegarde automatique rapport PDF...")
    pdf_file = pdf_report.save_report(
        original_note=resultat.original_note,
        step_logs=logs_avant_traitement + resultat.step_logs,
        ai_stream=resultat.ai_stream,
        processed_note=resultat.processed_note,
        correction_debrief=resultat.correction_debrief,
        token_stats=resultat.token_stats,
    )

    if pdf_file:
        log_message("🎉 SUCCÈS: Rapport PDF sauvegardé !")
        log_message(f"📁 Rapport PDF dans {config.REPORTS_DIR}")
    else:
        log_message("⚠️ ATTENTION: Sauvegarde PDF échouée")

    log_message("\n🎉 TERMINÉ: Traitement IA Gemini avec capture complète terminé !")
    return True


# --- Panneau de contrôle Tkinter avec thème Sun Valley ---

# Journal du panneau, rattaché au logger promptodys comme le reste du paquet.
# Deviendra logging.getLogger(__name__) quand le panneau rejoindra promptodys/presentation/
_logger = logging.getLogger("promptodys.presentation.control_panel")

# Délai maximum d'attente de la fermeture de l'éditeur avant de quitter quand même
CLOSE_EDITOR_TIMEOUT_S = 3


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

    L'état de l'éditeur est géré exclusivement par les événements de React et par le retour de
    editor_window.start() :
    - on_editor_open()  : _editor_open = True (React notifie l'ouverture), fin du lancement ;
    - on_editor_close() : _editor_open = False (React notifie la fermeture) ;
    - _launch_editor()  : _editor_open = False (editor_window.start() retourne, ou lève si crash).
    _editor_starting : du clic sur « Ouvrir l'éditeur » au signal de React (ou à l'échec).

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
        self._editor_open = False
        # Lancement demandé, en attente du signal de React (on_editor_open) : évite un second lancement
        self._editor_starting = False
        # Fermeture de l'éditeur demandée, en attente de sa confirmation : ignore un second clic sur Quitter
        self._closing = False
        # Timestamp de la dernière activité éditeur détectée
        self._last_editor_activity: float | None = None
        # Dossier du document courant (style Arduino : mémorise le dernier save/open)
        # Ex: "C:/.../PromptoDYS/MonDoc" → dialogue de sauvegarde pré-rempli
        self._current_document_path: str | None = None

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
        self._editor_open = True
        self._editor_starting = False  # Le lancement est terminé : l'éditeur est prêt
        self._last_editor_activity = time.time()  # Marquer l'activité
        self._in_ui_thread(lambda: self._status_label.config(text="✅ Éditeur ouvert"))

    def on_editor_close(self) -> None:
        """React signale la fermeture de l'éditeur"""
        self._editor_open = False
        self._last_editor_activity = None  # Réinitialiser le timestamp
        self._in_ui_thread(lambda: self._status_label.config(text="🔴 Éditeur fermé"))

    # --- Boutons ---

    def _open_editor(self) -> None:
        """Lance l'éditeur dans un thread séparé"""
        if self._editor_open:
            _logger.info("📝 L'éditeur est déjà ouvert")
            self._status_label.config(text="✅ L'éditeur est déjà ouvert")
            return

        if self._editor_starting:
            _logger.info("📝 L'éditeur est déjà en cours d'ouverture")
            self._status_label.config(text="⏳ Ouverture de l'éditeur en cours, veuillez patienter")
            return

        # Levé dès le clic : un second clic pendant l'attente du port ou de Chrome ne relance rien
        self._editor_starting = True
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
            self._editor_starting = False
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
            self._editor_open = False
            self._editor_starting = False
            self._show_launch_failure(
                "❌ Échec de l'ouverture de l'éditeur (voir les logs)",
                "L'éditeur n'a pas pu s'ouvrir.\n\n"
                "Vérifiez que Google Chrome est installé,\n"
                "puis réessayez.\n\n"
                "Le détail de l'erreur est dans la console.",
            )
            return

        # Quand l'éditeur se ferme, on met à jour le statut
        self._in_ui_thread(lambda: self._status_label.config(text="🔴 Éditeur fermé"))
        self._editor_open = False
        self._editor_starting = False  # Si React n'a jamais signalé l'ouverture

    def _save_document(self) -> None:
        """Sauvegarde le document — toujours en mode "Enregistrer sous" (dialogue à chaque fois).
        Si un document est déjà ouvert, le dialogue pré-remplit le nom et le dossier courant."""
        if not self._editor_open:
            messagebox.showwarning(
                "PromptoDYS - Éditeur requis",
                "L'éditeur n'est pas ouvert.\n\nVeuillez d'abord ouvrir l'éditeur\navant de sauvegarder.",
                icon="warning",
            )
            self._status_label.config(text="⚠️ Éditeur non ouvert")
            return

        _logger.info(
            f"🔍 DEBUG btn_sauvegarder: editeur_lance={self._editor_open}, "
            f"current_document_path={self._current_document_path}"
        )

        # Toujours afficher le dialogue — pré-rempli si document déjà ouvert/sauvegardé
        current_path = self._current_document_path
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
                self._current_document_path = result
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
        need_wait = not self._editor_open
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
                # Attendre le signal de React (on_editor_open → _last_editor_activity)
                timeout = 30
                waited = 0
                _logger.info("⏳ Attente du signal React on_editor_open()...")
                while self._last_editor_activity is None and waited < timeout:
                    time.sleep(0.5)
                    waited += 0.5

                if self._last_editor_activity is None:
                    _logger.info("❌ Timeout: React n'a pas signalé on_editor_open() dans les 30 secondes")
                    self._in_ui_thread(lambda: self._status_label.config(text="❌ Éditeur non prêt (timeout)"))
                    return

                # Petit délai pour laisser React finir l'initialisation complète des composants
                time.sleep(1.5)

            _logger.info("✅ Éditeur prêt, chargement du document...")

            result = documents.open_document(self._editor, self._store, selected_path)
            if result:
                # Mémoriser le dossier du document ouvert (comme Arduino retient le sketch ouvert)
                self._current_document_path = result
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
        if not self._editor_open:
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
        (on_editor_close ou retour de editor_window.start() remettent _editor_open à False), puis quitte.
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

        def wait_for_close() -> None:
            if not self._editor_open:
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

        if self._editor_open:
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


def main():
    """Lance l'application - GUI d'abord, éditeur via bouton"""
    # Avant la création de la fenêtre Tk, sinon l'interface est floue sous Windows
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)  # DPI per monitor
    except ImportError, AttributeError, OSError:
        pass  # Ignorer si non Windows

    configure_logger()
    log_message("🚀 Lancement de PromptoDYS...")
    log_message("💾 Sauvegarde automatique : PDF uniquement avec CAPTURE COMPLÈTE des logs")

    # Trouver le dossier web
    web_folder = config.find_web_folder()
    if not web_folder:
        log_message("💡 Placez votre build React dans le dossier 'build/'")
        return

    # Créer le dossier reports
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    log_message(f"📁 Dossier des rapports PDF : {config.REPORTS_DIR}")

    # Créer le dossier des documents et le profil Chrome de l'éditeur
    os.makedirs(config.PROMPTO_DOCS_DIR, exist_ok=True)
    log_message(f"📁 Dossier projets PromptoDYS : {config.PROMPTO_DOCS_DIR}")
    os.makedirs(config.CHROME_PROFILE_DIR, exist_ok=True)
    log_message(f"🌐 Profil Chrome PromptoDYS : {config.CHROME_PROFILE_DIR}")

    # Initialiser Eel (préparation, mais ne lance pas encore)
    eel_editor.init(web_folder)
    log_message("✅ Eel initialisé, prêt à lancer l'éditeur")

    # Construire le panneau de contrôle, puis lui transmettre les événements de React
    log_message("🖥️ Lancement du panneau de contrôle...")
    panel = ControlPanel(
        editor=editeur_eel,
        store=disk_document_store.DiskDocumentStore(),
        editor_window=eel_editor.EelWindow(config.EEL_PORT, config.CHROME_PROFILE_DIR),
        process_note=traitement_gemini,
        documents_dir=config.PROMPTO_DOCS_DIR,
        reports_dir=config.REPORTS_DIR,
        icon_path=os.path.join(config.RESOURCES_DIR, "assets", "prompto.png"),
    )
    eel_editor.set_event_handlers(panel.on_editor_open, panel.on_editor_close)

    # Lancer la GUI de contrôle (BLOQUANT - boucle principale)
    panel.run()

    log_message("🔚 Application fermée")


if __name__ == "__main__":
    main()
