# Step 12: RSS integration

In the 3-phase model, RSS readers are dump layers for phase 1: you subscribe to feeds without immediately judging whether each item is relevant. Only in phase 2 do you decide what goes into the vault.

## 12a. RSS feeds via NetNewsWire

NetNewsWire is a free, open-source RSS reader for macOS and iOS, with iCloud sync between both devices. It is the central dump layer for all RSS feeds — both academic and non-academic. This is especially true if you primarily work on iOS: the Zotero iOS app has no built-in RSS functionality, making NetNewsWire the most practical choice for all feeds.

**Install:**

```bash
brew install --cask netnewswire
```

Or download via [netnewswire.com](https://netnewswire.com).

**Recommended feeds:**
- Journal RSS (e.g. BMJ, NEJM, TSG)
- PubMed searches as RSS feed
- Policy sites and government newsletters
- Trade blogs and opinion pieces on health policy (e.g. Zorgvisie, Skipr)
- Substack publications by relevant authors (each has an RSS feed via `[name].substack.com/feed`)

**Useful RSS URLs:**

```
# PubMed search as RSS (replace the search term):
https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=[searchterm]&format=abstract

# Journal RSS (example BMJ):
https://www.bmj.com/rss/ahead-of-print.xml

# Google Scholar alerts (set up via email and forward, or via RSS-bridge)
```

> **Phase 1 → phase 2:** Items in NetNewsWire have not yet been saved — they only exist in your feed reader. This is intentional: you browse through them and scan headlines and intros without immediately archiving anything. Only what is truly relevant gets forwarded to the vault. That is the filter moment.

**From NetNewsWire to the vault (phase 2 → phase 3):**

Interesting articles are saved via two routes:

- **Via Zotero browser extension or iOS app:** open the article, click the Zotero icon → item is saved with metadata to Zotero `_inbox`. Use this route for academic articles where you want to retain BibTeX metadata and annotation capabilities.
- **Direct to `inbox/`:** pass the URL to Claude Code with the instruction `inbox [URL]` → Claude Code fetches the content and saves it as a Markdown file in `inbox/`, without Zotero. Use this route for non-academic articles, news items, and policy documents.

> **Privacy note:** NetNewsWire stores feed data locally. No reading habits are sent to external servers.

## 12b. Academic feeds: from NetNewsWire to Zotero

For academic articles from NetNewsWire, the recommended route is to always add them to Zotero first before having them processed. This way you have BibTeX metadata and annotation capabilities available:

1. Open the article from NetNewsWire in your browser
2. Click the Zotero icon in your browser (or use the Zotero iOS app) → item is saved to `_inbox`
3. Process from `_inbox` via type 0 → type 1 in the skill
