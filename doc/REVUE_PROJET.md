# Revue du projet PromptoDYS

> Passe de revue complète de l'application Python (dépôt `PromptoDYS_app`), à la recherche de problèmes et d'améliorations possibles.
>
> Date : 12/10/2026. Version revue : 1.2.0, commit `9e62040`. Périmètre : code Python, configuration PyInstaller, dépôt git, documentation, archives de distribution. L'éditeur React (dépôt `promptoDYS_editor`) n'est pas revu ici, seul son bundle compilé dans `build_web/` est examiné.
>
> **Aucune modification de code n'a été faite.** Ce document est un constat et un plan ; chaque correction attend un GO.
>
> **Mise à jour du 20/10/2026** (commit `b873d32`) : le statut de chaque constat traité depuis la revue est indiqué sous son titre et dans le [tableau récapitulatif](#11-tableau-récapitulatif). Résolus : C1, B7, M2, D2. Partiellement résolus : M1, M5, D3, D4, D5. Les numéros de ligne cités renvoient toujours au commit `9e62040` et ont pu bouger depuis.

---

## Sommaire

1. [Résumé en une page](#1-résumé-en-une-page)
2. [Méthode](#2-méthode)
3. [Constats critiques : sécurité](#3-constats-critiques--sécurité)
4. [Constats importants : bugs fonctionnels](#4-constats-importants--bugs-fonctionnels)
5. [Constats mineurs : qualité du code](#5-constats-mineurs--qualité-du-code)
6. [Dépôt, build et documentation](#6-dépôt-build-et-documentation)
7. [Améliorations possibles](#7-améliorations-possibles)
8. [Ce qui est bien fait](#8-ce-qui-est-bien-fait)
9. [Trois stratégies de remédiation](#9-trois-stratégies-de-remédiation)
10. [Plan d'action proposé](#10-plan-daction-proposé)
11. [Tableau récapitulatif](#11-tableau-récapitulatif)

---

## 1. Résumé en une page

Le projet fonctionne et rend un vrai service. Le cœur du produit (lecture de la note, prompt, streaming Gemini, injection, PDF) est robuste dans le cas nominal et bien documenté. La revue a tout de même relevé **deux problèmes de sécurité à traiter immédiatement**, **sept bugs fonctionnels** dont trois se combinent pour bloquer l'interface, et une série de points de dette technique.

Les cinq priorités, dans l'ordre :

1. **La clé API Gemini a été distribuée en clair** dans les deux archives de distribution (`PromptoDYS_v1.1.zip` et `promptoDYS_v1.2.zip`) et elle est en plus embarquée dans l'exécutable par le fichier spec. Elle doit être révoquée et régénérée. ✅ Fait le 20/10/2026.
2. **Le bouton "Traiter la prise de note" se bloque définitivement** quand le fichier de clé est absent : enchaînement de deux bugs (retour anticipé sans remise à zéro, puis plantage du failsafe sur une option Tkinter invalide). C'est exactement le scénario d'un nouvel utilisateur.
3. **La fenêtre de contrôle fait 1100 px de haut** avec un minimum à 1000 px : sur un portable d'élève en 1366×768, le bas de la fenêtre (console, bouton Quitter) est hors écran.
4. **Le code lit `GeminiKey.txt`, `promptodys.prompt` et écrit `reports/` dans le dossier courant**, pas dans le dossier de l'exécutable. Lancé depuis un raccourci, l'application ne trouve plus son prompt.
5. **Le dépôt transporte des fichiers morts** : trois anciens bundles React (environ 3,5 Mo) qui gonflent l'exécutable, un `requirements.txt` en UTF-16 illisible sur GitHub, et une documentation en partie obsolète (commande d'installation incomplète, menu console disparu).

---

## 2. Méthode

| Vérification | Outil | Résultat |
|---|---|---|
| Lecture intégrale de [askGeminiPrompto.py](../askGeminiPrompto.py) (1 784 lignes), du spec, du prompt, des docs | Lecture manuelle | Base de tous les constats |
| Analyse statique | `ruff check --select F,E9,B,W6` | 24 signalements, dont 2 vrais bugs (`F821`) |
| Imports inutiles, `except` nus, longueur des fonctions | Script AST maison | 3 imports morts, 4 `except:` nus, une fonction de 559 lignes |
| Option `style=` sur un `tk.Button` | Test Tkinter isolé | `TclError: unknown option "-style"` confirmé |
| Clé API dans l'historique git | `git log --all -- GeminiKey.txt` | Jamais commitée, c'est le bon point |
| Clé API dans les archives de distribution | `unzip -l` sur les deux zips | **Présente en clair dans les deux** |
| Bundles React réellement utilisés | `grep` sur `index.html` et les 4 `main.*.js` | Un seul bundle référencé, trois morts |
| Encodage de `requirements.txt` | `file` | UTF-16 LE avec BOM |

---

## 3. Constats critiques : sécurité

### C1. La clé API Gemini a été distribuée en clair

**Où.** Les deux archives présentes à la racine du projet (ignorées par git, mais ce sont celles qui ont été diffusées) :

- `PromptoDYS_v1.1.zip` contient `GeminiKey.txt` à la racine, avec une clé réelle.
- `promptoDYS_v1.2.zip` contient `dist/GeminiKey.txt`, avec une clé réelle.
- Le dossier `dist/` local contient aussi la clé, et `dist/readme.txt` la présente comme « votre clé API personnelle » alors que c'est celle du développeur.

En plus, [PromptoDYS.spec:13](../PromptoDYS.spec#L13) embarque `GeminiKey.txt` **dans l'exécutable**. N'importe qui peut l'extraire avec un outil comme `pyinstxtractor` en quelques secondes. Ce point est d'ailleurs déjà signalé dans [ARCHITECTURE.md](ARCHITECTURE.md), section 8, mais sans action.

**Pourquoi c'est grave.** Une clé Gemini diffusée peut être utilisée par n'importe qui, à vos frais et sous votre identité Google. Les quotas gratuits peuvent être épuisés et, si la facturation est activée, la note peut monter.

**Pistes.**
1. Révoquer la clé actuelle dans Google AI Studio et en créer une nouvelle. C'est à faire quoi qu'il arrive, et tout de suite.
2. Retirer la ligne `('GeminiKey.txt', '.')` du spec.
3. Ne plus jamais inclure de clé dans une archive : livrer un `GeminiKey.txt` vide ou un `GeminiKey.example.txt`, et laisser l'utilisateur créer le sien (c'est déjà ce que dit `BUILD_v1.2.0_SUCCESS.md`, mais l'archive ne le respecte pas).

**Effort.** Faible. Une ligne dans le spec, une régénération de clé, un nettoyage des archives.

**Statut : ✅ résolu.** Le spec n'embarque plus `GeminiKey.txt` (commit `184eb4f`), et ARCHITECTURE.md le rappelle. Les deux archives zip et le dossier `dist/` ne sont plus à la racine du projet. La clé diffusée a été révoquée dans Google AI Studio et remplacée (20/10/2026).

### C2. Les ressources embarquées ne sont jamais lues, et le chemin courant est roi

**Où.** [askGeminiPrompto.py:782](../askGeminiPrompto.py#L782) ouvre `"GeminiKey.txt"`, [askGeminiPrompto.py:816](../askGeminiPrompto.py#L816) ouvre `"promptodys.prompt"`, [askGeminiPrompto.py:728](../askGeminiPrompto.py#L728) crée `"reports"`. Ces trois chemins sont **relatifs au dossier courant** (celui depuis lequel le programme est lancé), pas au dossier de l'exécutable ni au dossier temporaire PyInstaller.

**Conséquences.**
- Le spec embarque `promptodys.prompt` et `GeminiKey.txt` dans l'exe, mais ces copies ne sont jamais lues. Pour la clé, c'est une exposition sans aucun bénéfice (voir C1).
- Lancé depuis un raccourci dont le champ « Démarrer dans » pointe ailleurs, ou depuis une invite de commande dans un autre dossier, l'application répond « Fichier promptodys.prompt introuvable » et crée `reports/` au mauvais endroit.
- En mode développement, `find_web_folder()` cherche `build_web/` depuis `.`, donc le script ne démarre que si on est dans le bon dossier.

**Piste.** Définir une fois pour toutes un `BASE_DIR` : le dossier de `sys.executable` quand on est dans l'exe, celui de `__file__` sinon. Puis construire tous les chemins avec `os.path.join(BASE_DIR, ...)`. Garder `promptodys.prompt` et `build_web/` embarqués via `sys._MEIPASS` comme valeur de secours est possible, mais pas la clé.

**Effort.** Faible à moyen. Une constante et cinq remplacements.

**Statut : 🟡 partiellement résolu.** Le prompt, renommé `prompto.dys` → `promptodys.prompt`, est désormais lu par `lire_prompto_dys()` dans `sys._MEIPASS` (copie embarquée) quand on tourne dans l'exe, et dans le dossier du script en développement. Il ne dépend plus du dossier courant, et un fichier placé à côté de l'exe est ignoré. Restent relatifs au dossier courant : `GeminiKey.txt`, `reports/` et `build_web/` en mode développement.

---

## 4. Constats importants : bugs fonctionnels

### B1. Le failsafe du bouton IA plante sur une option invalide

**Où.** [askGeminiPrompto.py:1403](../askGeminiPrompto.py#L1403) :

```python
btn_ia.configure(text="🤖 Traiter la prise de note", style="Big.TButton", state="normal")
```

`btn_ia` est un `tk.Button` classique (choix de la refonte GUI pour les bordures épaisses). L'option `style=` n'existe que sur les widgets `ttk`. Le test isolé confirme : `TclError: unknown option "-style"`. Le failsafe, censé « débloquer l'interface quoi qu'il arrive », plante donc avant d'avoir réactivé le bouton. L'exception sort dans la console Tkinter, et le bouton reste désactivé.

**Piste.** Supprimer `style="Big.TButton"`. Une ligne.

### B2. Un échec avant le streaming laisse le bouton en mode « Abandonner »

**Où.** [askGeminiPrompto.py:842](../askGeminiPrompto.py#L842) met `traitement_en_cours = True`, puis les étapes 1 et 3 font `return` ([ligne 857](../askGeminiPrompto.py#L857), [ligne 873](../askGeminiPrompto.py#L873)) **avant** le bloc `try/finally` de l'étape 6, qui est le seul endroit où le bouton et le drapeau sont remis à zéro.

**Scénario concret, celui d'un premier lancement sans clé :**
1. L'utilisateur clique sur « Traiter la prise de note ». Le bouton devient « ⛔ Abandonner le traitement ».
2. `init_gemini_client()` ne trouve pas `GeminiKey.txt`, la fonction sort. Le bouton reste sur « Abandonner », `traitement_en_cours` reste vrai.
3. [Ligne 1437](../askGeminiPrompto.py#L1437) affiche quand même « ✅ Traitement IA terminé ! », puisque `abandon_ia` est faux.
4. L'utilisateur, perplexe, clique sur « Abandonner ». Le bouton passe à « ⏳ Abandon en cours... » et se désactive.
5. Cinq secondes plus tard, le failsafe de B1 plante. **Le bouton est mort jusqu'au redémarrage.**

**Piste.** Encapsuler toute la fonction dans un `try/finally` unique, ou passer par une fonction interne `_traitement()` dont le retour est toujours suivi de la remise à zéro. Et faire remonter un succès/échec pour que le statut affiché soit juste.

**Effort.** Faible. Déplacement d'un `try`.

### B3. Deux messages d'erreur différés déclenchent un `NameError`

**Où.** [askGeminiPrompto.py:1243](../askGeminiPrompto.py#L1243) et [askGeminiPrompto.py:1442](../askGeminiPrompto.py#L1442), signalés par ruff (`F821 Undefined name 'e'`).

```python
except Exception as e:
    root.after(0, lambda: status_label.config(text=f"❌ Erreur: {str(e)[:30]}"))
```

En Python 3, la variable `e` d'un bloc `except` est **effacée à la sortie du bloc**. La lambda, elle, s'exécute plus tard dans la boucle Tkinter. Au moment où elle tourne, `e` n'existe plus : `NameError`. Résultat : l'erreur d'origine n'est jamais affichée dans la barre de statut, et une deuxième erreur s'ajoute à la première.

**Piste.** Capturer le texte avant : `msg = str(e)[:30]` puis `lambda: status_label.config(text=f"❌ Erreur: {msg}")`.

**Effort.** Trivial.

### B4. La fenêtre de contrôle ne tient pas sur un écran de portable

**Où.** [askGeminiPrompto.py:1472](../askGeminiPrompto.py#L1472) `root.geometry("688x1100")` et [ligne 1478](../askGeminiPrompto.py#L1478) `root.minsize(550, 1000)`.

| Écran | Hauteur utile (barre des tâches déduite) | Verdict |
|---|---|---|
| Portable 1366×768 (très courant chez les élèves) | ~720 px | 380 px de fenêtre hors écran, impossible à réduire |
| 1920×1080 | ~1040 px | Le bouton Quitter et la console sont coupés |
| 2560×1440 | ~1400 px | OK |

Le public cible (collégiens) utilise majoritairement des portables. Les boutons ont des bordures de 12 px, des polices de 16 et des marges de 15 px, ce qui explique la hauteur.

**Piste.** Lire `root.winfo_screenheight()` au démarrage, plafonner la hauteur à 90 % de l'écran, baisser `minsize` à ~650 px, et laisser la console de logs absorber l'espace restant (`expand=True`). Réduire légèrement bordures et paddings sur petit écran.

**Effort.** Faible.

### B5. Port 8080 fixe et relance de l'éditeur fragile

**Où.** [askGeminiPrompto.py:1223](../askGeminiPrompto.py#L1223) `port=8080`, avec en plus `'--app=http://localhost:8080/index.html'` en dur dans les arguments Chrome ([ligne 1225](../askGeminiPrompto.py#L1225)), alors qu'Eel ajoute déjà son propre `--app=`.

- Le port 8080 est l'un des plus utilisés au monde (serveurs de dev, proxys, certaines imprimantes). S'il est pris, `eel.start` échoue, et le fallback utilise... le même port.
- Quand l'utilisateur ferme la fenêtre Chrome, Eel sans `close_callback` appelle `sys.exit()` dans son thread. Le serveur gevent n'est pas arrêté proprement, le port peut rester occupé quelques secondes, et un second clic sur « Ouvrir l'éditeur » peut échouer.
- Le drapeau `editeur_lance` dépend du retour de `eel.start(block=True)`, ce qui est documenté comme « plus fiable que psutil » mais reste indirect.

**Piste.** `port=0` laisse Eel choisir un port libre (et il faut alors retirer le `--app=` manuel). Fournir un `close_callback` qui met `editeur_lance` à faux et arrête proprement le serveur.

**Effort.** Faible, mais à tester soigneusement (ouverture, fermeture, réouverture).

### B6. Aucun délai maximum sur l'appel Gemini, abandon inopérant si le flux se fige

**Où.** [askGeminiPrompto.py:921](../askGeminiPrompto.py#L921). Le client est créé sans `http_options`, donc sans timeout. Le drapeau `abandon_ia` n'est testé qu'à la réception d'un morceau. Si le réseau tombe en plein streaming sans fermer la connexion, le thread reste bloqué indéfiniment, et le failsafe de 5 s (une fois B1 corrigé) remet le bouton à « Prêt » alors que le thread tourne toujours. Un second clic lancerait un deuxième traitement en parallèle.

**Piste.** `genai.Client(api_key=..., http_options={'timeout': 120_000})` (en millisecondes dans ce SDK), et fermer explicitement l'itérateur de streaming lors d'un abandon (`stream.close()`).

**Effort.** Faible.

### B7. Chrome est lancé avec `--disable-web-security`

**Où.** [askGeminiPrompto.py:1226](../askGeminiPrompto.py#L1226).

Cette option désactive la politique de même origine pour toute la fenêtre. Elle n'est pas nécessaire ici : l'éditeur et Eel sont servis depuis la même origine `localhost`. Si l'éditeur charge un jour une ressource externe (bibliothèque, police, image), cette option supprime la protection du navigateur. Les autres options (`--disable-extensions`, `--no-first-run`) sont raisonnables.

**Piste.** Retirer l'option et vérifier que l'éditeur fonctionne toujours (il devrait).

**Effort.** Trivial, un test à faire.

**Statut : ✅ résolu.** L'option a été retirée (commit `b873d32`), en même temps que l'ajout d'un profil Chrome dédié (`--user-data-dir`). Jusque-là, l'option était en fait ignorée par Chrome, qui ne l'applique qu'avec un profil séparé. Avec le profil dédié, elle devenait active et Chrome affichait le bandeau « flag de ligne de commande non pris en charge ». L'éditeur ne charge que des ressources servies par Eel sur `localhost` et des URL `blob:` et `data:`, qui n'ont pas besoin de cette option.

---

## 5. Constats mineurs : qualité du code

### M1. Imports et dépendances inutilisés

- `import markdown` ([ligne 33](../askGeminiPrompto.py#L33)), `PageBreak` ([ligne 44](../askGeminiPrompto.py#L44)), `TableOfContents` ([ligne 45](../askGeminiPrompto.py#L45)) : jamais utilisés. Le spec déclare aussi `'markdown'` en `hiddenimports`.
- `psutil` est dans `requirements.txt` mais plus dans le code (l'ancienne détection par processus a été retirée).
- La docstring d'en-tête parle de `PromptoDYS.py` et de `build/index.html`, qui n'existent pas.

**Statut : 🟡 partiellement résolu.** Les trois imports morts ont été retirés, ainsi que la dépendance `markdown` (`pyproject.toml`, `uv.lock`, `hiddenimports` du spec). `psutil` a disparu avec `requirements.txt` (voir D2). La docstring d'en-tête ne cite plus `PromptoDYS.py`, mais mentionne toujours `build/index.html` (le dossier est `build_web/`) et une « Interface console » qui n'existe plus.

### M2. Code mort

- `menu_console()`, `lire_contenu()`, `ecrire_contenu()` ([lignes 1059 à 1143](../askGeminiPrompto.py#L1059-L1143)) : l'ancien menu console, jamais appelé depuis la refonte GUI, mais toujours documenté dans le README.
- `historique_llm` et `ajouter_message_llm()` : rempli à chaque traitement, jamais lu.
- `web_folder_global` : déclaré global, utilisé uniquement dans `main()`.

**Statut : ✅ résolu.** Le menu console (`menu_console()`, `lire_contenu()`, `ecrire_contenu()`) a été supprimé (commit `793fe44`), et le README ne le décrit plus. `historique_llm` et `ajouter_message_llm()` ont été supprimés, ainsi que l'étape 11 « Historique de session » du traitement IA, qui en compte désormais dix. `web_folder_global` est devenue une variable locale de `main()`.

### M3. Signalements ruff automatiquement corrigeables

Quatre `except:` nus (lignes 64, 104, 110, 117) qui attrapent aussi `KeyboardInterrupt` et `SystemExit`. Vingt f-strings sans variable (`f"..."` sans accolades), sans effet mais qui brouillent la lecture. `ruff check --fix` règle l'ensemble.

### M4. Un fichier de 1 784 lignes, une fonction de 559 lignes, douze variables globales

`gui_control_panel()` contient six fonctions imbriquées, la construction de l'interface, la redirection de stdout et la boucle principale. `traitement_gemini()` fait 221 lignes. L'état est partagé par des `global` (`editeur_lance`, `abandon_ia`, `traitement_en_cours`, `btn_ia_global`, `root_global`, `status_label_global`, `streaming_text_global`, `current_document_path`, `last_editor_activity`, `logs_complets`, `historique_llm`, `web_folder_global`).

Ce n'est pas un bug, mais c'est ce qui a rendu B1 et B2 possibles : l'état du bouton est modifié depuis quatre endroits différents. Le découpage naturel, qui suit déjà les commentaires de section du fichier :

| Module proposé | Contenu | Lignes actuelles |
|---|---|---|
| `config.py` | `BASE_DIR`, `__version__`, modèle, port, chemins | éparpillé |
| `gemini_client.py` | `init_gemini_client`, `lire_prompto_dys`, `extraire_*`, `traitement_gemini` | 772 à 1054 |
| `rapport_pdf.py` | `preparer_contenu_rapport_complet`, `convertir_markdown_vers_paragraphes`, `generer_pdf_reportlab`, `sauvegarder_rapport` | 458 à 750 |
| `documents.py` | `save_document`, `load_document`, `_get_documents_folder` | 191 à 410 |
| `bridge_eel.py` | `get_markdown`, `set_markdown`, `on_editor_open/close`, `find_web_folder` | 132 à 455 |
| `gui.py` | `gui_control_panel` et ses boutons, `RedirectText` | 1146 à 1752 |
| `askGeminiPrompto.py` | `main()` seulement | 1755 à 1784 |

### M5. Les dix premiers caractères de la clé API sont écrits dans les logs et archivés dans le PDF

[Ligne 777](../askGeminiPrompto.py#L777). Ces logs sont copiés dans la section 3 du rapport PDF. Les six premiers caractères sont communs à toutes les clés Google, donc la fuite réelle est de quatre caractères. Faible, mais sans utilité : un simple « Clé API chargée (39 caractères) » suffit.

**Statut : 🟡 partiellement résolu.** La portion loggée a été raccourcie : le log n'affiche plus que les 4 derniers caractères de la clé (`Clé API chargée (...xxxx)`) au lieu des 10 premiers, ce qui suffit à identifier la clé utilisée sans exposer de partie exploitable. Le log se trouve désormais dans `init_gemini_client()`. Pour résoudre complètement, ne logger aucun extrait (longueur de la clé uniquement).

### M6. Nom de fichier image non assaini à la sauvegarde

[Ligne 289](../askGeminiPrompto.py#L289) : `os.path.join(images_dir, image["filename"])` utilise tel quel un nom venant du JavaScript. Un nom contenant `..\` écrirait hors du dossier `images/`. Le risque réel est faible (tout est local), mais `os.path.basename()` règle la question en un mot.

### M7. Double avertissement « Balises NOTE absentes »

`extraire_contenu_note()` ([ligne 819](../askGeminiPrompto.py#L819)) et `traitement_gemini()` ([ligne 992](../askGeminiPrompto.py#L992)) testent tous deux la présence des balises et loggent le même message. Un seul test suffirait.

### M8. Le parseur Markdown du PDF a des trous prévisibles

- Les émojis sont retirés par une **liste fixe** ([ligne 591](../askGeminiPrompto.py#L591)). Tout émoji absent de la liste devient un carré noir avec Helvetica. Le prompt lui-même impose « 😉 » dans la section Avertissement, et il n'est pas dans la liste : **chaque rapport PDF contient un carré noir** dans la note corrigée. Les icônes des logs (🖼️, 🟢, ⛔, 🚫, 📌, 📡) non plus.
- L'italique en ligne est détecté par `\*([^*]+)\*` ([ligne 661](../askGeminiPrompto.py#L661)), ce qui abîme les formules du type `$a*b*c$` et les multiplications dans les notes de maths.
- Les listes numérotées (`1)`, `1.`) ne sont pas reconnues et sortent en texte brut.

**Piste.** Remplacer la liste d'émojis par une plage Unicode (`[\U0001F300-\U0001FAFF☀-➿]`), ou mieux, enregistrer une police Unicode dans ReportLab. Le projet embarque déjà `OpenDyslexic-Regular.otf` et `Lexend` dans `build_web/fonts/` : les utiliser dans le PDF rendrait les rapports eux-mêmes lisibles par le public DYS (voir A1).

### M9. La console de logs Tkinter grossit sans limite

`update_streaming_text()` insère sans jamais purger. Chaque morceau de streaming ajoute une ligne. Sur une session d'une après-midi avec plusieurs traitements, le widget `Text` accumule des centaines de kilo-octets et ralentit. Une purge au-delà de 2 000 lignes règle le problème en trois lignes.

### M10. `root.after()` appelé depuis des threads secondaires

C'est le mécanisme utilisé partout pour revenir sur le thread Tkinter. Il fonctionne en pratique sur CPython Windows, mais il n'est pas garanti thread-safe par Tk. Le symptôme classique est un `RuntimeError: main thread is not in main loop` à la fermeture. Le remplacement par une `queue.Queue` lue par un `root.after(100, poll)` est l'approche documentée. À faire seulement si le symptôme apparaît.

### M11. Fermeture par `os._exit(0)`

[Ligne 1183](../askGeminiPrompto.py#L1183). La fenêtre Chrome reste ouverte après la fermeture du panneau, et rien n'est flushé proprement. Un `eel`-side `close` ou un `close_callback` (voir B5) permettrait une sortie plus nette.

### M12. Effets de bord à l'import

[Lignes 207 à 209](../askGeminiPrompto.py#L207-L209) créent `Documents\PromptoDYS` et impriment, au moment où le module est importé. Cela empêche d'importer le fichier dans un test sans toucher au disque. À déplacer dans `main()`.

**Mise à jour du 20/10/2026.** Le commit `b873d32` ajoute un second effet de bord du même type : `CHROME_PROFILE_DIR = _get_chrome_profile_dir()` crée le dossier du profil Chrome dédié à l'import. À déplacer dans `main()` avec le premier.

---

## 6. Dépôt, build et documentation

### D1. Trois anciens bundles React traînent dans `build_web/`

`index.html` et `asset-manifest.json` référencent `main.63c59ca4.js`. Les fichiers `main.6fd5b08d.js`, `main.e1572bd0.js`, `main.ea163566.js` et leurs `.map` et `.LICENSE.txt` sont des restes de copies précédentes (le commit `811c1b1` en a ajouté deux d'un coup).

| Effet | Détail |
|---|---|
| Exécutable gonflé | Le spec inclut tout `build_web/static/`, donc environ 3,5 Mo de JS mort plus environ 5 Mo de source maps partent dans l'exe. |
| Démarrage ralenti | `eel.init()` ouvre et scanne chaque `.js` du dossier pour y trouver les `expose()`. |
| Confusion | Deux des vieux bundles n'exposent pas `readDocumentData`. En cas de régression d'`index.html`, le diagnostic serait pénible. |

**Piste.** Dans la procédure de copie (section 6 d'ARCHITECTURE.md), vider `build_web/static/` avant de copier. Exclure les `.map` du spec, ils ne servent qu'au débogage dans le navigateur.

### D2. `requirements.txt` est en UTF-16

**Statut : ✅ résolu.** `requirements.txt` a été supprimé au profit de uv : dépendances directes dans `pyproject.toml`, versions figées avec hashes dans `uv.lock`.

Signature d'un `pip freeze > requirements.txt` sous PowerShell 5. `pip` le lit grâce au BOM, mais GitHub l'affiche en caractères chinois, `git diff` le traite en binaire, et tout outil tiers (Dependabot, un `cat`) échoue. Le fichier est aussi un gel complet avec 40 dépendances transitives, ce qui masque les cinq vraies : `eel`, `google-genai`, `reportlab`, `sv-ttk`, et `pyinstaller` pour le build.

**Piste.** `pip freeze | Out-File -Encoding utf8 requirements.txt`, ou mieux un `requirements.txt` court à la main et un `requirements-lock.txt` gelé.

### D3. Documentation en partie obsolète ou contradictoire

| Fichier | Problème | Statut |
|---|---|---|
| [README.md](../README.md) | La commande `pip install eel google-genai reportlab markdown` **oublie `sv_ttk`** : un nouveau contributeur obtient `ModuleNotFoundError` au premier lancement. Même oubli dans `README_ANTIVIRUS.md` et `BUILD_STATUS.md`. | ✅ Résolu : installation par `uv sync --locked` dans README.md et README_ANTIVIRUS.md |
| README.md | Décrit un « menu console avec 3 options » qui n'existe plus, une structure avec `/REPORTS` et `data/` (le code écrit `reports/`, `data/` n'est utilisé nulle part), « 848 lignes » (il y en a 1 784), « Python 3.8+ » alors que le build se fait en 3.13. | 🟡 Partiel : menu console, nombre de lignes et version de Python corrigés ; la structure liste encore `data/` |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Parle de la branche `main`, le dépôt utilise `master`. Le remote `upstream` pointe sur `ORIGINAL_OWNER/PromptoDYS`, un reste de gabarit. | ❌ À faire |
| `BUILD_STATUS.md` | Décrivait un problème Python 3.10.0 résolu depuis, et contredisait `BUILD_v1.2.0_SUCCESS.md`. | ✅ Supprimé |
| [README_ANTIVIRUS.md](../README_ANTIVIRUS.md) | Lien VirusTotal « [À ajouter après build] » depuis janvier. | ❌ À faire |
| `.env.template` | Le nom suggère un fichier `.env`, c'est en fait le gabarit de `GeminiKey.txt`. `GeminiKey.example.txt` serait plus clair. | ✅ Résolu : renommé en [GeminiKey.txt.template](../GeminiKey.txt.template), visible même avec les extensions masquées dans Windows, et livré avec la notice [LISEZMOI.txt](../LISEZMOI.txt) |
| [CHANGELOG.md](../CHANGELOG.md) 1.2.0 | Annonce « Métadonnées Windows complètes », mais la ligne `version='version_info.txt'` est **commentée** dans le spec. L'exe n'a donc pas de métadonnées, ce qui aggrave les faux positifs antivirus que le même changelog prétend réduire. | ❌ À faire |
| [promptodys.prompt](../promptodys.prompt) | Accolade `}` orpheline ligne 28 (le bloc `{` ouvert ligne 2 est déjà fermé ligne 6), « faire » pour « faite », « a colorer », « meme ». Gemini s'en accommode, mais c'est le cerveau pédagogique du produit. | 🟡 Partiel : accolade orpheline et « faite » corrigés (commit `564d873`) ; restent « a colorer » et « meme » |

### D4. Le numéro de version est dupliqué à quatre endroits

`__version__` dans le code, le badge du README, `version_info.txt` et le CHANGELOG. Rien ne les relie. Le `__version__` du code n'est d'ailleurs lu nulle part (il pourrait au moins apparaître dans le titre de la fenêtre et dans le pied du rapport PDF, qui affiche en dur « Gemini 3.8 Flash »).

**Statut : 🟡 partiellement résolu.** Le pied du rapport PDF affiche maintenant la constante `GEMINI_MODEL` au lieu d'un nom de modèle en dur. La constante `__version__`, jamais lue, a été supprimée. La version de référence est celle de `pyproject.toml`, que le workflow de release compare au tag. Restent dupliqués à la main : le badge du README, `version_info.txt` (désactivé dans le spec) et le CHANGELOG.

### D5. Fichiers volumineux dans le dépôt et à sa racine

- Le PDF « Procédure complète - Création d'un exécutable PyInstaller » (946 Ko) est versionné. Il doublonne ARCHITECTURE.md section 6 et les deux fichiers BUILD_*.
- Deux archives de 39 et 45 Mo et un `build backup 290825.zip` vivent à la racine du projet (ignorés par git, mais synchronisés par Dropbox). Leur place est dans une release GitHub.

**Statut : 🟡 partiellement résolu.** Les archives zip ne sont plus à la racine du projet, et les livrables sont désormais publiés en Release GitHub par le workflow [release-windows.yml](../.github/workflows/release-windows.yml). Le PDF de procédure est toujours versionné.

### D6. Aucun test automatisé

Déjà noté dans les docs. Ce qui rend la chose facile à démarrer : plusieurs fonctions sont **pures** (pas d'interface, pas de réseau) et testables en dix lignes chacune :

- `extraire_contenu_note()`, `extraire_debrief_correction()` : avec et sans balises, avec marqueurs `__BOLD_n__`.
- `nettoyer_html_tags()` et `convertir_markdown_vers_paragraphes()` : titres, listes, bloc de code, émojis, `<span>`.
- `lire_prompto_dys()` : fichier sans `[TEXTE]`.
- La logique anti-récursion de `btn_sauvegarder_document` (à extraire dans une fonction).

Dix tests `pytest` suffiraient à protéger le cœur contre les régressions, notamment pendant le découpage M4.

---

## 7. Améliorations possibles

Ce sont des propositions, pas des défauts. Elles ne sont pas demandées et restent à valider une par une (règle YAGNI).

| Réf. | Proposition | Intérêt | Effort |
|---|---|---|---|
| A1 | Rapport PDF en police OpenDyslexic ou Lexend (déjà dans `build_web/fonts/`) | Les rapports deviennent lisibles par le public cible, et M8 disparaît | Faible |
| A2 | Lire la clé dans la variable d'environnement `GEMINI_API_KEY` en priorité, fichier en secours | Plus de clé sur disque pour qui le souhaite, compatible avec la pratique courante | Faible |
| A3 | Regrouper modèle, `thinking_budget`, température, port, dimensions de fenêtre en constantes de tête de fichier (ou dans `config.yaml` qui existe déjà) | Changer de modèle sans chercher dans 1 784 lignes | Faible. 🟡 En partie fait : `GEMINI_MODEL` et `GEMINI_THINKING_LEVEL` sont des constantes (commit `3339731`) ; port et dimensions de fenêtre restent en dur |
| A4 | Nommer le rapport PDF d'après le document courant (`rapport_MonCours_20261012_1530.pdf`) | Retrouver un rapport parmi cinquante | Faible |
| A5 | Journal sur disque via le module `logging` (fichier `promptodys.log` avec rotation) | Diagnostiquer un problème chez un utilisateur sans lui demander de copier la console | Faible |
| A6 | Afficher le coût estimé d'un traitement à partir des tokens | Sensibiliser à la consommation | Faible |
| A7 | Proposer la sauvegarde avant de fermer si l'éditeur est ouvert, au lieu du seul avertissement | Moins de notes perdues | Moyen |
| A8 | Tester la clé API au démarrage (un appel `count_tokens` léger) et afficher un message clair | Évite le scénario B2 et guide le premier lancement | Faible |

---

## 8. Ce qui est bien fait

Il est utile de le dire, pour ne pas y toucher pendant la remédiation.

- **La clé n'a jamais été commitée.** Le `.gitignore` et le `.gitattributes` sont complets et en place depuis le premier commit.
- **Le traitement IA est lisible** : onze étapes numérotées, logs explicites, deux accumulateurs distincts (réponse seule, flux complet), extraction tolérante aux balises manquantes.
- **Le streaming avec abandon** est la bonne architecture, et le `finally` de l'étape 6 est au bon endroit pour le cas nominal.
- **La sauvegarde « façon Arduino »** (dossier = nom du document, images à côté) est simple, explicable à un élève, et compatible avec l'éditeur seul.
- **L'attente du vrai signal React** (`on_editor_open`) avant de charger un document, avec timeout, est plus fiable que l'ancienne détection par processus.
- **La documentation technique** (ARCHITECTURE.md, WORKFLOW_GEMINI.md) est à jour, précise et honnête sur les points faibles. Peu de projets de cette taille l'ont.
- **Le bouton Ouvrir lance l'éditeur si besoin**, le dialogue de sauvegarde se souvient du dernier dossier, et la protection anti-récursion `equations/equations/` montre que les cas réels ont été rencontrés et traités.

---

## 9. Trois stratégies de remédiation

### Option 1 : corrections ciblées, fichier inchangé

Corriger C1, C2, B1 à B7, M1, M3, M5 à M7, D1 à D3 dans le fichier actuel, sans le découper.

- **Avantages.** Chaque correction fait une à dix lignes. Faible risque, revue facile, livrable en une session. Aucun impact sur la procédure de build.
- **Inconvénients.** Le fichier reste à 1 784 lignes avec ses douze globales ; le prochain bug de même nature que B1/B2 reste probable. Pas de tests.
- **Quand la choisir.** Si l'objectif est une version 1.2.1 rapide et sûre pour les utilisateurs actuels.

### Option 2 : corrections ciblées, puis découpage en modules avec tests

Option 1, puis M4 (six modules) et D6 (dix tests sur les fonctions pures), en deux lots distincts et deux commits.

- **Avantages.** Les tests écrits avant le découpage garantissent qu'il ne casse rien. Le découpage rend l'état du bouton local à `gui.py` et supprime la majorité des `global`. Conforme aux règles de travail du projet (un fichier par responsabilité, KISS).
- **Inconvénients.** Deux à trois sessions. Le spec PyInstaller doit être vérifié (les modules locaux sont détectés automatiquement, mais il faut rebuilder et retester l'exe). Les docs ARCHITECTURE.md et WORKFLOW_GEMINI.md doivent être mises à jour pour les nouveaux noms de fichiers.
- **Quand la choisir.** Si le projet doit continuer à évoluer (export DOCX, interface professeurs, prévus dans le CHANGELOG).

### Option 3 : refonte autour d'une classe d'application

Remplacer les globales par une classe `PromptoApp` qui porte l'état (éditeur, traitement, document courant) et expose les actions des boutons comme méthodes ; le reste comme l'option 2.

- **Avantages.** État unique, testable, plus de `global`. C'est la structure « propre » d'une application Tkinter.
- **Inconvénients.** Réécriture de la quasi-totalité du fichier. Risque de régression élevé sans tests d'interface, qui n'existent pas et sont coûteux à écrire. Rupture avec le style procédural que les docs et le CONTRIBUTING décrivent. Contraire au principe de simplicité pour un projet maintenu par une personne.
- **Quand la choisir.** Pas maintenant.

**Recommandation : l'option 2.** L'option 1 d'abord, parce que les quatre premiers constats ne peuvent pas attendre. Puis le découpage, parce que le CHANGELOG annonce des évolutions et que la structure actuelle rendra chacune plus risquée. L'option 3 n'apporte pas assez pour son coût.

---

## 10. Plan d'action proposé

Chaque lot est un commit. Chaque étape attend un GO et s'accompagne d'une mise à jour de la todo list.

### Lot 0 : sécurité, hors code (à faire aujourd'hui)

1. Révoquer la clé Gemini actuelle dans Google AI Studio et en générer une nouvelle. Mettre à jour `GeminiKey.txt` local. ✅ Fait (20/10/2026).
2. ✅ Fait : `dist/` et les deux archives zip ne sont plus à la racine du projet. ~~Supprimer `dist/GeminiKey.txt`, et retirer la clé des deux archives zip (ou supprimer les archives).~~

### Lot 1 : corrections ciblées (une session)

| # | Fichier | Action | Constat |
|---|---|---|---|
| 1 | `PromptoDYS.spec` | 🟡 En partie fait : `('GeminiKey.txt', '.')` retiré. Restent : réactiver `version='version_info.txt'`, exclure les `.map` | C1, D3 |
| 2 | `askGeminiPrompto.py` | Introduire `BASE_DIR`, l'utiliser pour clé, prompt, `reports/`, `build_web/` | C2 |
| 3 | `askGeminiPrompto.py` | Supprimer `style="Big.TButton"` ligne 1403 | B1 |
| 4 | `askGeminiPrompto.py` | Englober `traitement_gemini()` dans un `try/finally` unique, retourner un booléen, corriger le statut ligne 1437 | B2 |
| 5 | `askGeminiPrompto.py` | Capturer `str(e)` avant les deux lambdas (lignes 1243, 1442) | B3 |
| 6 | `askGeminiPrompto.py` | Hauteur de fenêtre calculée depuis l'écran, `minsize` à 650 | B4 |
| 7 | `askGeminiPrompto.py` | 🟡 En partie fait : `--disable-web-security` retiré. Restent : `port=0`, retirer le `--app=` manuel, ajouter `close_callback` | B5, B7 |
| 8 | `askGeminiPrompto.py` | `http_options` avec timeout, fermeture du stream à l'abandon | B6 |
| 9 | `askGeminiPrompto.py` | 🟡 En partie fait : imports morts, `menu_console` et compagnie, `historique_llm` retirés. Restent : `ruff --fix` ; `basename` sur le nom d'image ; log de clé sans extrait | M1, M2, M3, M5, M6, M7 |
| 10 | `build_web/static/` | Supprimer les trois vieux bundles et leurs `.map` | D1 |
| 11 | `requirements.txt` | ✅ Fait : remplacé par `pyproject.toml` + `uv.lock` | D2 |
| 12 | `README.md`, `CONTRIBUTING.md`, `BUILD_STATUS.md`, `GeminiKey.txt.template`, `promptodys.prompt` | 🟡 En partie fait : corrections listées en D3, voir la colonne Statut | D3 |
| 13 | Build | `pyinstaller --clean`, test sur machine sans clé, avec clé, depuis un raccourci | Validation |

### Lot 2 : tests sur les fonctions pures (une demi-session)

14. Créer `tests/test_extraction.py` et `tests/test_pdf_markdown.py`, dix tests `pytest`, sans réseau ni interface.

### Lot 3 : découpage en modules (une à deux sessions)

15. Déplacer les blocs selon le tableau de M4, un module par commit, en relançant les tests à chaque étape.
16. Mettre à jour ARCHITECTURE.md et WORKFLOW_GEMINI.md (noms de fichiers, section 7).
17. Rebuild et test de l'exe.

### Lot 4 : améliorations (à la demande)

18. A1 (police DYS dans le PDF) et A8 (test de clé au démarrage) sont les deux qui apportent le plus pour le moins d'effort.

---

## 11. Tableau récapitulatif

| Réf. | Gravité | Constat | Effort | Lot |
|---|---|---|---|---|
| C1 | ✅ Résolu | Clé API distribuée dans les zips et embarquée dans l'exe (plus embarquée, zips retirés, clé révoquée) | Faible | 0, 1 |
| C2 | 🔴 Critique | Chemins relatifs au dossier courant ; ressources embarquées jamais lues | Faible | 1 |
| B1 | 🟠 Important | Failsafe du bouton plante (`style=` sur `tk.Button`) | Trivial | 1 |
| B2 | 🟠 Important | Retour anticipé sans reset : bouton bloqué, faux statut « terminé » | Faible | 1 |
| B3 | 🟠 Important | `NameError` dans deux messages d'erreur différés | Trivial | 1 |
| B4 | 🟠 Important | Fenêtre de 1100 px hors écran sur portable | Faible | 1 |
| B5 | 🟠 Important | Port 8080 fixe, relance fragile, `--app` dupliqué | Faible | 1 |
| B6 | 🟠 Important | Pas de timeout Gemini, abandon inopérant si flux figé | Faible | 1 |
| B7 | ✅ Résolu | `--disable-web-security` inutile (retiré) | Trivial | 1 |
| M1 | 🟡 Partiellement résolu | Imports et dépendances inutilisés (retirés ; docstring d'en-tête encore obsolète) | Trivial | 1 |
| M2 | ✅ Résolu | Code mort (menu console, historique, `web_folder_global`) | Trivial | 1 |
| M3 | 🟡 Mineur | `except:` nus, f-strings vides | Trivial | 1 |
| M4 | 🟡 Mineur | Fichier monolithique, douze globales | Moyen | 3 |
| M5 | 🟡 Partiellement résolu | Extrait de clé dans les logs et le PDF (raccourci aux 4 derniers caractères) | Trivial | 1 |
| M6 | 🟡 Mineur | Nom d'image non assaini | Trivial | 1 |
| M7 | 🟡 Mineur | Double avertissement NOTE | Trivial | 1 |
| M8 | 🟡 Mineur | Parseur PDF : émojis (carré noir garanti), italique vs maths, listes numérotées | Faible | 1 ou 4 |
| M9 | 🟡 Mineur | Console Tk sans purge | Trivial | 1 |
| M10 | 🟡 Mineur | `root.after` depuis threads | Faible | si symptôme |
| M11 | 🟡 Mineur | `os._exit`, Chrome reste ouvert | Faible | 1 |
| M12 | 🟡 Mineur | Effets de bord à l'import (un second ajouté : dossier du profil Chrome) | Trivial | 2 |
| D1 | 🟠 Important | Trois bundles React morts, `.map` dans l'exe | Trivial | 1 |
| D2 | ✅ Résolu | `requirements.txt` en UTF-16 (remplacé par uv) | Trivial | 1 |
| D3 | 🟡 Partiellement résolu | Docs obsolètes, `sv_ttk` absent de la commande d'installation, `version=` commenté (installation et README corrigés ; restent CONTRIBUTING, VirusTotal, `version=`) | Faible | 1 |
| D4 | 🟡 Partiellement résolu | Version dupliquée quatre fois (modèle du pied PDF via `GEMINI_MODEL` ; version toujours dupliquée) | Faible | 3 |
| D5 | 🟡 Partiellement résolu | Archives et PDF lourds dans le dépôt ou à la racine (archives retirées ; PDF toujours versionné) | Trivial | 1 |
| D6 | 🟡 Mineur | Aucun test | Faible | 2 |
