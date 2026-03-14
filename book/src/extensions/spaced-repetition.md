# Step 13: Spaced repetition (Obsidian plugin)

The Obsidian Spaced Repetition plugin uses the SM-2 algorithm to schedule flashcards based on how well you know them. Cards are created in your Markdown files and reviewed within Obsidian.

## 13a. Install plugin

1. Open Obsidian
2. Go to **Settings → Community Plugins → Browse community plugins**
3. Search for "Spaced Repetition"
4. Install the plugin by Stephen Mwangi
5. Enable the plugin via the toggle

## 13b. Flashcard format

Cards are created in regular Markdown files using the `?` separator:

```markdown
#flashcard

What is the definition of substitution care?
?
Care that is moved from secondary to primary care, maintaining quality but at lower cost.

What are the three pillars of the Integrated Care Agreement?
?
1. Appropriate care
2. Regional collaboration
3. Digitalization and data exchange
```

Cards can be in the same file as the literature note or written to `flashcards/`. The recommended approach is to place cards **in the note itself**: this keeps the card connected to its context and source reference, and during review you can immediately see where a concept came from. The `flashcards/` folder is intended for standalone concept cards that are not tied to one specific source — for example definitions or principles you want to remember independently of a paper.

## 13c. Claude Code generates flashcards automatically

After creating a literature note, you can ask Claude Code to generate flashcards:

```
Create 3–5 flashcards for the literature note just created.
Use the Obsidian Spaced Repetition format with ? as separator.
```

Claude Code adds the cards to the end of the existing note (or writes them to `flashcards/[same name].md`).

## 13d. Daily review

1. Open Obsidian
2. Click the card icon in the right sidebar (or use `Cmd + Shift + R`)
3. Review the cards scheduled for today: **Easy / Good / Hard**
4. The plugin automatically schedules the next review based on your rating

> **Privacy note:** All cards and review data are stored as local files in your vault. No cloud sync is required.
