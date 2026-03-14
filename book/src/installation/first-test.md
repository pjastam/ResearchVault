# Step 9: Run first test

## 9a. Start Zotero

Make sure Zotero 7 is open and active (the local API is only available when Zotero is running).

## 9b. Open Claude Code in your vault

```bash
cd ~/Documents/ResearchVault
claude
```

## 9c. Run test prompts

Try the following prompts in Claude Code to verify everything works:

**Test 1 — Zotero connection:**
```
Search my Zotero library for recent additions and give an overview.
```

**Test 2 — Retrieve a paper:**
```
Find a paper about [a topic you have in Zotero] and write a literature note
to literature/ in Obsidian format.
```

**Test 3 — Semantic search:**
```
Use semantic search to find papers that are conceptually related to [topic].
```

**Test 4 — Vault awareness:**
```
Look at the structure of this vault and give a summary of what is already in it.
```

If all four tests work, the basic installation is complete.
