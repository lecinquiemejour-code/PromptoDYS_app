# Note pour le dev Front-End : Bug `readDocumentData()` retourne un objet vide

**Date :** 19/02/2026  
**Priorité :** Bloquant (la sauvegarde Python ne fonctionne pas)  
**Auteur :** Équipe Python/Eel

---

## Contexte

On a implémenté côté Python les fonctions de sauvegarde/ouverture de documents complets (texte + images) selon la spec `SPEC_EDITEUR_ET_BRIDGE_PYTHON.md`. Le Python appelle les 2 nouvelles fonctions Eel exposées par le hook `useEelBridge.js` :

- `readDocumentData()` — pour récupérer le contenu à sauvegarder
- `writeDocumentData(data)` — pour injecter un document dans l'éditeur

---

## Ce qui marche

### `writeDocumentData(data)` — OK (partiellement)

L'appel suivant **fonctionne** — le document s'affiche correctement dans l'éditeur (texte + image) :

```python
data = {
    "markdown": "# Mon cours\n\nDu texte...\n\n![photo](./images/photo.png){width=300px id=abc123}\n",
    "images": [
        {
            "filename": "photo.png",
            "data": "iVBORw0KGgoAAAANSUhEUgAA...",   # base64 pur
            "mimeType": "image/png"
        }
    ]
}
result = eel.writeDocumentData(data)()
```

**Observation :** Le document s'affiche bien dans l'éditeur, MAIS la fonction retourne `None` au lieu de `True`. Ce n'est pas bloquant (on gère le cas), mais il serait bien d'ajouter un `return true;` explicite côté JS.

---

## Ce qui NE marche PAS

### `readDocumentData()` — KO (retourne `{}` vide)

```python
data = eel.readDocumentData()()
# Résultat : {} (dictionnaire vide, aucune clé)
```

### Logs de debug complets

```
🔍 DEBUG: editeur_lance=True, last_editor_activity=1771519205.0870059
🔍 DEBUG: Appel eel.readDocumentData()()...
🔍 DEBUG readDocumentData retour → type=dict
🔍 DEBUG readDocumentData → dict avec clés: []
❌ SAUVEGARDE: Aucune donnée reçue de l'éditeur (data est falsy: {})
```

### Ce qu'on attend (selon la spec)

```python
data = eel.readDocumentData()()
# Doit retourner :
{
    "markdown": "# Mon cours\n\nDu texte...\n\n![photo](./images/photo.png){width=300px id=abc123}\n",
    "images": [
        {
            "filename": "photo.png",
            "data": "iVBORw0KGgoAAAANSUhEUgAA...",   # base64 pur (PAS de préfixe data:image/...)
            "mimeType": "image/png"
        }
    ]
}
```

### Ce qu'on reçoit

```python
{}   # dict vide — ni markdown, ni images
```

---

## Points de vérification côté JS

### 1. La fonction `readDocumentData` est-elle bien exposée à Eel ?

Elle doit être exposée avec `window.eel.expose()` dans le hook `useEelBridge.js` :

```javascript
window.eel.expose(readDocumentData, 'readDocumentData');
```

**Vérification :** La fonction EXISTE bien côté Eel (pas d'exception Python). Le problème est qu'elle retourne un objet vide.

### 2. La fonction lit-elle le bon état ?

Elle doit récupérer :
- Le **contenu Markdown** actuel de l'éditeur (même source que `readMarkdown()` qui lui fonctionne)
- Les **images stockées en IndexedDB** (ou dans le state React), encodées en base64 pur

### 3. La fonction retourne-t-elle bien le résultat ?

Vérifier qu'il y a un **`return`** explicite :

```javascript
// ❌ Problème probable : pas de return, ou return d'un objet vide
function readDocumentData() {
    // ... code qui prépare les données ...
    // return manquant ou return {} ?
}

// ✅ Ce qu'il faut :
function readDocumentData() {
    const markdown = getMarkdownContent();  // même source que readMarkdown()
    const images = getImagesFromIndexedDB(); // ou depuis le state React
    return {
        markdown: markdown,
        images: images   // tableau d'objets {filename, data, mimeType}
    };
}
```

### 4. Est-ce un problème async ?

Si la fonction est **async** (ex: accès IndexedDB), Eel ne gère pas nativement les Promises. Il faut utiliser un callback ou résoudre la Promise avant de retourner :

```javascript
// ❌ Ne marchera PAS avec Eel (retourne une Promise, pas les données)
async function readDocumentData() {
    const images = await getImagesFromDB();
    return { markdown, images };
}

// ✅ Solution avec callback Eel
function readDocumentData() {
    // Si synchrone : return direct
    return { markdown: getMarkdown(), images: getImagesSync() };
}

// ✅ Ou si async obligatoire : utiliser eel.expose avec un callback
function readDocumentData(callback) {
    getImagesFromDB().then(images => {
        // Retourner via return pour Eel
        return { markdown: getMarkdown(), images: images };
    });
}
```

**C'est probablement la cause la plus probable** : si `readDocumentData` est async (à cause d'IndexedDB), elle retourne une Promise que Python reçoit comme `{}`.

---

## Rappel du format attendu

### `readDocumentData()` → doit retourner :

```javascript
{
    markdown: "# Titre\n\nTexte...\n\n![alt](./images/photo.png){width=300px id=uuid}\n",
    images: [
        {
            filename: "photo.png",           // nom du fichier (correspond au chemin dans le MD)
            data: "iVBORw0KGgoAAAANSUhEUg...", // base64 PUR (pas de préfixe data:image/png;base64,)
            mimeType: "image/png"
        }
    ]
}
```

- Si pas d'images → `images: []`
- Le `data` est du base64 **pur** : pas de `data:image/png;base64,` devant
- Le `filename` correspond au nom dans le Markdown : `./images/{filename}`

### `writeDocumentData(data)` → doit retourner `true` ou `false` :

Même format en entrée. Actuellement retourne `undefined` (non bloquant, mais à corriger).

---

## Pour tester

Côté Python, les logs de debug sont déjà en place. Après correction JS, relancer l'appli et cliquer "Sauvegarder" → les logs afficheront :

```
🔍 DEBUG readDocumentData → dict avec clés: ['markdown', 'images']
🔍 DEBUG   markdown: 1321 caractères
🔍 DEBUG   images: 1 image(s)
```

Si tu vois ça, c'est gagné.

---

## Résumé

| Fonction | État | Problème |
|---|---|---|
| `readMarkdown()` | ✅ OK | Fonctionne (existant) |
| `writeMarkdown()` | ✅ OK | Fonctionne (existant) |
| `writeDocumentData(data)` | ⚠️ Partiel | Le document se charge, mais retourne `undefined` au lieu de `true` |
| `readDocumentData()` | ❌ KO | Retourne `{}` au lieu de `{markdown, images}` — **probablement un problème async/return** |
