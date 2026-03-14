# Step 2: Install and configure Zotero 7

## 2a. Download Zotero

Download Zotero 7 via [zotero.org](https://www.zotero.org/download/). Install the application by opening the `.dmg` and dragging Zotero to your Applications folder.

## 2b. Enable the local API

This is the crucial step that makes Zotero MCP possible:

1. Open Zotero
2. Go to **Zotero → Settings → Advanced** (or `Cmd + ,`)
3. Scroll down to the **Other** section
4. Check the box next to **"Allow other applications on this computer to communicate with Zotero"**
5. Note the port number that appears (default: `23119`)

> **Privacy note:** This API is only accessible via `localhost` — no external access is possible.

## 2c. Verify the local API is working

Open a new tab in your browser and go to:

```
http://localhost:23119/
```

You should see a JSON response with version information from Zotero. If that works, the local API is functioning correctly.

## 2d. Create `_inbox` collection (central collection bucket)

In the 3-phase model, Zotero's `_inbox` collection is not a source in itself, but the central collection bucket where all sources flow: documents via the Zotero Connector or iOS app, RSS items via NetNewsWire, podcasts and videos via the Zotero iOS share sheet, and emails or notes via the iOS share button. You evaluate the content only in phase 2 (see step 14).

1. In Zotero, right-click **My Library** → **New Collection**
2. Name the collection `_inbox` (the underscore ensures it appears at the top of the list)
3. Set this as the default destination in the Zotero Connector: open the browser extension → **Settings** → set the default collection to `_inbox`
4. Set the same default on iOS: open the Zotero app → **Settings** → set the default collection location to `_inbox`

From now on, everything you save via the Connector or the iOS share sheet automatically goes to `_inbox`. You can also create a note directly within the Zotero app itself — it also ends up in `_inbox` if you have set that as the default.

## 2e. Install Better BibTeX plugin (recommended)

Better BibTeX significantly improves annotation extraction:

1. Download the latest `.xpi` from [retorque.re/zotero-better-bibtex/installation](https://retorque.re/zotero-better-bibtex/installation/)
2. In Zotero: **Tools → Plugins → Gear icon → Install from file**
3. Select the downloaded `.xpi` file
4. Restart Zotero
