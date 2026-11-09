# Architecture et fonctionnement de PromptoDYS

> Document de référence pour comprendre comment les deux projets (application Python et éditeur React) coopèrent, du clic de l'élève jusqu'au rapport PDF.
>
> Dernière mise à jour : 09/11/2026. Les schémas sont en Mermaid et se rendent directement dans GitHub, VS Code et la plupart des visionneuses Markdown.

---

## Sommaire

1. [Les deux dépôts](#1-les-deux-dépôts)
2. [Les trois acteurs qui tournent en même temps](#2-les-trois-acteurs-qui-tournent-en-même-temps)
3. [Le pont Eel : quatre fonctions, un seul langage commun](#3-le-pont-eel--quatre-fonctions-un-seul-langage-commun)
4. [Le traitement IA de bout en bout](#4-le-traitement-ia-de-bout-en-bout)
5. [Sauvegarde et ouverture d'un document avec images](#5-sauvegarde-et-ouverture-dun-document-avec-images)
6. [La chaîne de fabrication : deux dépôts, un seul exécutable](#6-la-chaîne-de-fabrication--deux-dépôts-un-seul-exécutable)
7. [Fichiers clés](#7-fichiers-clés)
8. [Points d'attention](#8-points-dattention)

---

## 1. Les deux dépôts

PromptoDYS est composé de deux projets indépendants, hébergés sur deux dépôts GitHub distincts du même compte.

| Projet | Rôle | Dépôt | Dossier local |
|---|---|---|---|
| **PromptoDYS_app** | Application Python : panneau de contrôle, appel à Gemini, rapports PDF, sauvegarde sur disque. Contient le bundle React **compilé**. | https://github.com/lecinquiemejour-code/PromptoDYS_app | `PythonProjects/PromptoDYS` |
| **promptoDYS_editor** | Éditeur React accessible aux dyslexiques. Contient les **sources** React. | https://github.com/lecinquiemejour-code/promptoDYS_editor | `CascadeProjects/editor` |

L'application Python ne contient pas le code source de l'éditeur, seulement sa version compilée dans `build_web/`. Voir la section 6 pour la chaîne de fabrication.

---

## 2. Les trois acteurs qui tournent en même temps

Quand on lance PromptoDYS, un seul programme Python démarre, mais il fait vivre trois choses à la fois : une petite fenêtre de contrôle Tkinter, un mini serveur web Eel, et une fenêtre Chrome qui affiche l'éditeur React.

Python et l'éditeur ne partagent pas de mémoire : ils se parlent par un tuyau WebSocket que gère Eel.

```mermaid
flowchart LR
    subgraph PY["Processus Python : paquet promptodys/"]
        TK["Panneau de contrôle Tkinter<br/>Ouvrir l'éditeur, Sauvegarder, Ouvrir,<br/>Traiter la note, Voir les rapports"]
        EEL["Serveur Eel<br/>port 8080<br/>sert build_web/ et fait le pont"]
        IA["Module Gemini<br/>prompt + streaming"]
        PDF["Module ReportLab<br/>rapport PDF"]
    end

    subgraph CHROME["Fenêtre Chrome en mode application"]
        REACT["Éditeur React<br/>Editor, Toolbar, StatusBar"]
        BRIDGE["useEelBridge.js<br/>5 fonctions exposées à Python"]
        IDB["IndexedDB + localStorage<br/>images, thème, brouillon"]
    end

    GEMINI["API Google Gemini 3.8 Flash"]
    DISK["Disque<br/>Documents/PromptoDYS/*.md + images/<br/>reports/*.pdf"]

    TK --> EEL
    TK --> IA
    TK --> PDF
    EEL <-- "WebSocket" --> BRIDGE
    BRIDGE <--> REACT
    REACT <--> IDB
    IA <-- "HTTPS" --> GEMINI
    PDF --> DISK
    TK --> DISK
```

**Le point clé :** l'éditeur ne connaît pas Gemini, et Python ne connaît pas le HTML de l'éditeur. Chacun reste dans son rôle, et le pont Eel ne transporte que du Markdown.

### Rôle de chaque acteur

- **Panneau Tkinter** ([promptodys/presentation/control_panel.py](../promptodys/presentation/control_panel.py), classe `ControlPanel`) : chef d'orchestre. Cinq boutons, une barre de statut, une console de logs. Chaque action longue tourne dans un thread séparé pour ne pas figer la fenêtre ; ces threads ne touchent à l'interface que par `_in_ui_thread()`.
- **Serveur Eel** : préparé par `eel_editor.init(build_web)` au démarrage, puis lancé par `eel_editor.start(...)` quand on clique sur Ouvrir l'éditeur ([promptodys/infrastructure/eel_editor.py](../promptodys/infrastructure/eel_editor.py)). Il sert les fichiers statiques de l'éditeur et maintient le WebSocket.
- **Éditeur React** : zone d'édition WYSIWYG, barre d'outils, thème DYS, lecture vocale, formules MathJax. Il fonctionne aussi seul dans un navigateur, sans Python.
- **Stockage navigateur** : les images insérées sont copiées en IndexedDB, le brouillon et le thème en localStorage. Cela survit à un rafraîchissement de page.

### Organisation du code Python

Le code Python est dans le paquet `promptodys/`, en trois couches et un module d'assemblage (voir [RECOMMANDATIONS.md](RECOMMANDATIONS.md), priorité 3). La règle de dépendance `presentation → domain ← infrastructure` est vérifiée par import-linter (`uv run lint-imports`, et en CI), ainsi qu'une quatrième règle : aucune couche n'importe le module d'assemblage.

| Couche | Contenu | État |
|---|---|---|
| `promptodys/domain/` | Règles métier et cas d'usage, sans Tk, Eel, Gemini ni reportlab : `note.py` (prompt, extraction de la réponse, note d'origine), `report.py` (contenu du rapport), `documents.py` (chemins de sauvegarde, cas d'usage sauvegarder et ouvrir), `processing.py` (cas d'usage du traitement IA), `ports.py` (ports `Editor`, `AIModel`, `DocumentStore` et données échangées) | Fait |
| `promptodys/infrastructure/` | Adaptateurs des ports et accès au monde extérieur : `eel_editor.py` (adaptateur `EelEditor`, fenêtre de l'éditeur, événements de React, port du serveur), `gemini_model.py` (`GeminiModel`, client Gemini), `disk_document_store.py` (`DiskDocumentStore`), `pdf_report.py` (rapport PDF ReportLab), `config.py` (modèle Gemini, chemins, port, clé API, modèle de prompt) | Fait |
| `promptodys/presentation/` | `control_panel.py` : panneau de contrôle Tkinter (`ControlPanel`), `EditorWindow` (ce que le panneau attend de la fenêtre de l'éditeur), `RedirectText` (stdout et stderr vers la console du panneau). N'importe ni l'infrastructure, ni Eel, Gemini ou reportlab | Fait |
| `promptodys/app.py` | Assemblage, hors des couches : `main()`, `run_processing()` (traitement IA, étapes 1, 2 et 9), journalisation provisoire | Fait |

Le point d'entrée est `main()` dans [promptodys/app.py](../promptodys/app.py). On le lance par `uv run python askGeminiPrompto.py`, enveloppe gardée pour [PromptoDYS.spec](../PromptoDYS.spec), la release et la documentation, ou par `uv run python -m promptodys`.

Les adaptateurs héritent explicitement de leur port (`class EelEditor(ports.Editor)`), et pyright vérifie leur conformité. `main()` les instancie et les passe au panneau, qui les transmet aux cas d'usage du domaine. La fenêtre de l'éditeur arrive au panneau sous la forme d'un `EelWindow`, que pyright confronte au Protocol `EditorWindow` de la présentation sans que l'infrastructure ait à l'importer. Les signaux d'ouverture et de fermeture envoyés par React arrivent dans `eel_editor`, qui les transmet à `ControlPanel.on_editor_open()` et `on_editor_close()`, enregistrées par `main()` avec `set_event_handlers()` : l'infrastructure ne touche jamais à l'interface.

---

## 3. Le pont Eel : quatre fonctions, un seul langage commun

Le fichier `src/hooks/useEelBridge.js` de l'éditeur expose quatre fonctions que Python peut appeler comme si elles étaient locales. **Python parle toujours Markdown.** C'est l'éditeur qui convertit vers ou depuis son HTML interne.

```mermaid
flowchart TB
    subgraph PYTHON["Côté Python"]
        P1["eel.readMarkdown()()"]
        P2["eel.writeMarkdown(md)"]
        P3["eel.readDocumentData()()"]
        P4["eel.writeDocumentData(data)()"]
        P5["@eel.expose on_editor_open()<br/>@eel.expose on_editor_close()"]
        P6["eel.closeEditor()"]
    end

    subgraph JS["Côté React"]
        J1["readMarkdown<br/>HTML du DOM → Markdown"]
        J2["writeMarkdown<br/>Markdown → HTML → injecte dans le DOM"]
        J3["readDocumentData<br/>Markdown + images en base64<br/>lues depuis le DOM via canvas"]
        J4["writeDocumentData<br/>base64 → blob URL → HTML → DOM<br/>+ copie en IndexedDB"]
        J5["Au montage / démontage<br/>signale l'état à Python"]
        J6["closeEditor<br/>window.close()"]
    end

    P1 --> J1
    P2 --> J2
    P3 --> J3
    P4 --> J4
    J5 --> P5
    P6 --> J6
```

| Fonction | Sens | Usage | Format échangé |
|---|---|---|---|
| `readMarkdown` | Python lit l'éditeur | Traitement IA | Markdown (texte seul) |
| `writeMarkdown` | Python écrit dans l'éditeur | Injection de la note corrigée | Markdown (texte seul) |
| `readDocumentData` | Python lit l'éditeur | Sauvegarde complète | `{ markdown, images: [{filename, data, mimeType}] }` |
| `writeDocumentData` | Python écrit dans l'éditeur | Ouverture complète | Même structure |
| `on_editor_open` / `on_editor_close` | React signale Python | État de l'éditeur, activation des boutons | Aucun paramètre |
| `closeEditor` | Python ferme l'éditeur | Fermeture du panneau de contrôle avec l'éditeur ouvert | Aucun paramètre |

### Règle technique importante

Eel ne sait pas attendre une promesse JavaScript. **Les fonctions exposées doivent être synchrones.** Une fonction `async` renvoie une promesse, que Python reçoit comme un dictionnaire vide. C'est la cause du bug corrigé le 19/02/2026 (voir [NOTE_POUR_DEV_FRONTEND.md](../NOTE_POUR_DEV_FRONTEND.md)).

Conséquence : pour la sauvegarde, les images sont lues directement dans les pixels affichés, via un `canvas`, plutôt que depuis IndexedDB qui est asynchrone.

### Convention Markdown des images

Dans le Markdown échangé, une image s'écrit avec ses attributs entre accolades :

```markdown
![photo](./images/photo_20260212_143022_0.png){width=300px id=a1b2c3d4-...}
```

- `./images/<filename>` : chemin relatif au dossier du document.
- `width` / `height` : dimensions choisies dans l'éditeur.
- `id` : identifiant interne IndexedDB. Python ne le génère pas et ne le modifie pas, il le préserve tel quel.

---

## 4. Le traitement IA de bout en bout

C'est le cœur du produit. Tout part du bouton **Traiter la prise de note**, et tout se termine par un PDF d'archive.

```mermaid
sequenceDiagram
    actor U as Élève
    participant TK as Panneau Tkinter
    participant R as Éditeur React
    participant G as Gemini
    participant D as Disque

    U->>R: Tape sa note (texte, images, formules)
    U->>TK: Clic "Traiter la prise de note"
    TK->>TK: Thread séparé, bouton devient "Abandonner"
    TK->>R: eel.readMarkdown()
    R->>R: HTML du DOM → Markdown
    R-->>TK: Markdown de la note
    TK->>TK: Lit promptodys.prompt, remplace [TEXTE] et [DATE]
    TK->>G: generate_content_stream (GEMINI_MODEL, GEMINI_THINKING_LEVEL)
    loop Streaming
        G-->>TK: morceaux de réflexion 💭 et de réponse
        TK->>TK: Affiche dans la console, vérifie le jeton d'annulation
    end
    TK->>TK: Extrait le contenu entre NOTE et /NOTE
    TK->>TK: Ajoute la note d'origine (sans les images)
    TK->>R: eel.writeMarkdown(note corrigée)
    R->>R: Nettoie les astérisques, Markdown → HTML, injecte
    R-->>U: Note corrigée affichée, formules rendues par MathJax
    TK->>D: Rapport PDF complet dans reports/
    TK->>TK: Bouton redevient "Traiter la prise de note"
```

### Les étapes dans le code Python

Le traitement suit neuf étapes numérotées dans ses logs. La fonction `run_processing()` de [promptodys/app.py](../promptodys/app.py) fait les étapes qui dépendent de l'infrastructure (1, 2 et 9). Elle confie les étapes 3 à 8 au cas d'usage `process_note()` de [promptodys/domain/processing.py](../promptodys/domain/processing.py), qui renvoie un résultat sans toucher à l'interface.

1. Initialisation du client Gemini (clé lue dans `GeminiKey.txt`) et de sa configuration : modèle `GEMINI_MODEL` (`gemini-3.8-flash`) et niveau de réflexion `GEMINI_THINKING_LEVEL` (`LOW`), deux constantes en tête de [promptodys/infrastructure/config.py](../promptodys/infrastructure/config.py).
2. Lecture du template [promptodys.prompt](../promptodys.prompt).
3. Lecture du Markdown de l'éditeur.
4. Substitution de `[TEXTE]` et `[DATE]`.
5. Streaming de la réponse, avec vérification du jeton d'annulation à chaque morceau.
6. Extraction du contenu entre `<NOTE>` et `</NOTE>`, puis ajout de la note d'origine sans les images.
7. Injection dans l'éditeur.
8. Bilan des tokens (entrée, sortie, réflexion).
9. Génération du rapport PDF avec ReportLab.

### Le rôle de promptodys.prompt

Le fichier [promptodys.prompt](../promptodys.prompt) est le cerveau pédagogique. Il impose à Gemini :

- une structure en **sept sections** : titre, résumé, mots-clés, note corrigée, avertissement, doutes, questions. La note d'origine est ajoutée ensuite par Python, copie exacte sans les images ;
- une **fidélité au contenu** : aucune information supprimée ni ajoutée, les doutes sont signalés au lieu d'être corrigés ;
- **pas d'italique**, difficile à lire pour les dyslexiques ;
- des **titres colorés** en `#3399ff` ;
- les **balises `<NOTE>`** qui permettent à Python de séparer la note corrigée du débrief.

Si Gemini oublie les balises, Python injecte toute la réponse. C'est le cas dégradé prévu.

### Le rapport PDF

Son contenu est assemblé en Markdown par `build_report_markdown()` ([promptodys/domain/report.py](../promptodys/domain/report.py)), puis rendu par `generate_pdf()` ([promptodys/infrastructure/pdf_report.py](../promptodys/infrastructure/pdf_report.py)). Il contient le contenu original, les logs de traitement, le flux complet de réflexion et de réponse, la note finale, le débrief et les statistiques de tokens. Un parseur Markdown maison convertit le texte en paragraphes ReportLab, en supprimant les balises `<span>` et les émojis non supportés.

---

## 5. Sauvegarde et ouverture d'un document avec images

La convention choisie est celle de l'Arduino : **un dossier qui porte le nom du document**, contenant un fichier `.md` du même nom et un sous-dossier `images/`.

```
MonDocument/
├── MonDocument.md
└── images/
    ├── photo_20260212_143022_0.png
    └── schema_20260212_150530_1.png
```

Le dossier par défaut est `Documents\PromptoDYS` de l'utilisateur Windows.

```mermaid
sequenceDiagram
    actor U as Élève
    participant TK as Panneau Tkinter
    participant R as Éditeur React
    participant D as Documents/PromptoDYS

    rect rgb(235, 245, 255)
    note over U,D: Sauvegarder
    U->>TK: Clic "Sauvegarder", choisit un nom
    TK->>R: eel.readDocumentData()
    R->>R: Pour chaque image affichée : canvas → base64
    R->>R: Remplace les src par ./images/nom.png
    R->>R: HTML → Markdown
    R-->>TK: { markdown, images: [ {filename, data, mimeType} ] }
    TK->>D: MonDoc/MonDoc.md
    TK->>D: MonDoc/images/*.png (base64 décodé)
    end

    rect rgb(240, 255, 240)
    note over U,D: Ouvrir
    U->>TK: Clic "Ouvrir", choisit le .md
    TK->>TK: Lance l'éditeur si fermé, attend on_editor_open
    TK->>D: Lit le .md et encode chaque image en base64
    TK->>R: eel.writeDocumentData({ markdown, images })
    R->>R: base64 → Blob → URL blob
    R->>R: Markdown → HTML, remplace ./images/ par les URL blob
    R->>R: Injecte dans le DOM, copie en IndexedDB
    R-->>U: Document affiché, MathJax relancé
    end
```

Le résultat sur disque est volontairement **identique** à ce que produisent les boutons de sauvegarde internes à l'éditeur en mode navigateur. Un document sauvé par l'un s'ouvre avec l'autre.

Côté Python, les cas d'usage `save_document()` et `open_document()` de [promptodys/domain/documents.py](../promptodys/domain/documents.py) relient l'éditeur (adaptateur `EelEditor`, qui convertit les images entre base64 et binaire) et le disque (adaptateur `DiskDocumentStore`, dans [promptodys/infrastructure/disk_document_store.py](../promptodys/infrastructure/disk_document_store.py)). Le chemin du dernier document ouvert ou sauvé est mémorisé pour pré-remplir le dialogue suivant.

---

## 6. La chaîne de fabrication : deux dépôts, un seul exécutable

Les deux projets se rejoignent par une **copie manuelle du build** de l'éditeur dans l'application Python.

```mermaid
flowchart LR
    subgraph ED["Dépôt promptoDYS_editor"]
        SRC["src/ React<br/>17 fichiers"]
        BUILD["npm run build"]
        OUT["build/<br/>index.html, static/js, fonts"]
        SRC --> BUILD --> OUT
    end

    COPY["Copie manuelle"]

    subgraph APP["Dépôt PromptoDYS_app"]
        WEB["build_web/<br/>bundle React compilé"]
        PYS["askGeminiPrompto.py (enveloppe)<br/>promptodys/<br/>promptodys.prompt<br/>assets/prompto.png"]
        SPEC["PromptoDYS.spec<br/>PyInstaller"]
        EXE["dist/PromptoDYS.exe<br/>tout embarqué"]
        WEB --> SPEC
        PYS --> SPEC
        SPEC --> EXE
    end

    OUT --> COPY --> WEB
```

### Procédure quand l'éditeur change

1. Dans `CascadeProjects/editor` : modifier les sources, puis `npm run build`.
2. Vider `build_web/static/`, puis copier le contenu de `build/` dans `PythonProjects/PromptoDYS/build_web/`. Sans ce nettoyage, les anciens bundles s'accumulent : ils partent dans l'exécutable et Eel les parcourt au démarrage.
3. Vérifier que `build_web/index.html` référence bien le nouveau bundle `main.<hash>.js`.
4. Commiter dans **les deux** dépôts.

### Procédure pour produire l'exécutable

**Voie recommandée : l'intégration continue.** Le workflow [release-windows.yml](../.github/workflows/release-windows.yml) builde l'exe sur un runner Windows GitHub, quel que soit le système du développeur. Un tag `v*` publie la Release (voir [CONTRIBUTING.md](../CONTRIBUTING.md#publier-une-version)), un lancement manuel produit un artefact de test. Le workflow [ci.yml](../.github/workflows/ci.yml) relance ruff, import-linter, pyright, pytest et le build à chaque push, sur toutes les branches, sans rien publier.

**Build en local**, qui ne donne un `.exe` que sur Windows (PyInstaller produit un exécutable pour le système qui le lance) :

```powershell
uv sync --locked
uv run pyinstaller --clean PromptoDYS.spec
```

Le résultat est `dist/PromptoDYS.exe`. Voir aussi [README_ANTIVIRUS.md](../README_ANTIVIRUS.md).

---

## 7. Fichiers clés

### Application Python (`PromptoDYS_app`)

| Fichier | Rôle |
|---|---|
| [askGeminiPrompto.py](../askGeminiPrompto.py) | Point d'entrée historique : simple enveloppe de `promptodys.app.main()` |
| [promptodys/app.py](../promptodys/app.py) | Assemblage des couches dans `main()`, traitement IA `run_processing()`, journalisation provisoire |
| [promptodys/domain/](../promptodys/domain/) | Couche domaine : règles métier, cas d'usage et ports (voir [§2](#organisation-du-code-python)) |
| [promptodys/infrastructure/](../promptodys/infrastructure/) | Couche infrastructure : adaptateurs Eel, Gemini, disque et PDF, configuration |
| [promptodys/presentation/](../promptodys/presentation/) | Couche présentation : panneau de contrôle Tkinter |
| `tests/` | Tests pytest : `tests/domain/` pour la couche domaine (avec de faux adaptateurs), `tests/infrastructure/` pour les adaptateurs (Eel et Gemini simulés, vrai disque dans un dossier temporaire), `tests/presentation/` pour le panneau (fenêtre cachée, éditeur, fenêtre et traitement simulés), `tests/test_app.py` pour l'assemblage du traitement IA |
| [promptodys.prompt](../promptodys.prompt) | Template du prompt envoyé à Gemini |
| `GeminiKey.txt` | Clé API, **ignoré par git**, à créer depuis [GeminiKey.txt.template](../GeminiKey.txt.template) |
| [LISEZMOI.txt](../LISEZMOI.txt) | Notice d'installation pour l'utilisateur final, livrée dans le zip de release |
| [PromptoDYS.spec](../PromptoDYS.spec) | Configuration PyInstaller |
| `build_web/` | Éditeur React compilé, copié depuis le projet editor |
| `build_web/config.yaml` | Mode développeur de l'éditeur (lu au premier lancement seulement) |
| `reports/` | Rapports PDF générés, ignoré par git |

### Éditeur React (`promptoDYS_editor`)

| Fichier | Rôle |
|---|---|
| `src/hooks/useEelBridge.js` | Les quatre fonctions exposées à Python |
| `src/utils/markdownConverter.js` | Conversion HTML vers Markdown et retour |
| `src/utils/imageStore.js` | Stockage des images en IndexedDB |
| `src/components/Editor.js` | Zone d'édition WYSIWYG, sélection images et formules |
| `src/components/Toolbar.js` | Barre d'outils, sauvegarde et ouverture en mode navigateur |
| `src/hooks/useThemeSettings.js` | Thème DYS : couleurs, police, interlignage, espacement |
| `src/hooks/useTextToSpeech.js` | Lecture vocale avec surlignage mot à mot |
| `src/hooks/useMathJax.js` | Rendu des formules et enrichissement `data-tex` pour la sauvegarde |
| `SPEC_EDITEUR_ET_BRIDGE_PYTHON.md` | Spécification du pont, côté éditeur |

---

## 8. Points d'attention

- **Clé API hors de l'exécutable.** Le spec n'embarque pas `GeminiKey.txt` : chaque utilisateur place son propre fichier à côté de l'exe. Ne jamais embarquer de clé dans un exécutable distribué, ni commiter un exe dans un dépôt.
- **Droits de la CI.** Dans le workflow de release, seul le job `release` peut écrire sur le dépôt (`contents: write`), et il ne récupère ni n'exécute le code. Le job `build`, qui installe les dépendances et lance PyInstaller, tourne avec un jeton en lecture seule qu'il ne garde pas dans `.git/config` (`persist-credentials: false`).
- **Fonctions Eel synchrones uniquement.** Toute nouvelle fonction exposée à Python doit être synchrone (voir section 3).
- **Convertisseur Markdown à base d'expressions régulières.** Il gère les cas courants mais reste fragile sur le HTML imbriqué. C'est le point le plus sensible du pont, puisque tout ce que Gemini renvoie passe par là.
- **Mode développeur persistant.** Il est stocké dans le localStorage de Chrome et prime sur `config.yaml`. Une fois activé, modifier le YAML ne suffit plus pour le désactiver.
- **Images blob non persistantes.** En mode desktop, une image affichée via une URL blob ne survit pas à un redémarrage de Chrome. La sauvegarde Python compense en lisant les pixels dans le DOM.
- **Copie manuelle du build.** Rien ne garantit automatiquement que `build_web/` est à jour des sources de l'éditeur. Comparer les empreintes des fichiers `main.<hash>.js` en cas de doute.
- **Tests automatisés côté Python seulement.** L'application a des tests pytest (domaine, adaptateurs, assemblage du traitement IA), lancés en CI. L'éditeur React n'en a pas.
