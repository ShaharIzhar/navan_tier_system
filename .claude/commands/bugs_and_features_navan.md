Read the Apple Note titled "bugs and feature navan" with the Apple Notes MCP tool `mcp__apple-notes__get-note-markdown` (argument `title: "bugs and feature navan"`). Use this tool, not `get-note-content`: only the Markdown read shows which checklist items are ticked (`[x]`) and which are open (`[ ]`).

If the note can't be found or read, say so and stop. Do not write or overwrite the file.

If the Markdown has no `[x]` / `[ ]` markers at all, the tool could not read checklist state (it needs Full Disk Access). Say so and stop without writing the file, because finished items can't be told apart from open ones.

An **open item** is a checklist line marked `[ ]`. Skip every item marked `[x]` or `[X]`.

Classify each open item into one of two categories:
- **Bugs**: Issues, broken behavior, UI glitches, things that are malfunctioning or not working as expected.
- **Features / Todos**: Enhancements, improvements, design requests, or new functionality to add.

Then write the file at:
`/Users/shaharizhar/Public/repos/navan_tier_system/bugs_and_todos.md`

Use this exact format:

```
# Navan — Bugs & Todos
_Last synced: <today's date and time>_

## 🐛 Bugs

- [ ] <bug item>

## ✨ Features / Todos

- [ ] <feature item>
```

Rules:
- Only include open/unchecked items. Skip any item that is checked off (marked with `[x]`, `[X]`, or otherwise completed).
- Replace the file contents entirely — do not keep old items that are no longer in the note.
- If an item is ambiguous, use your best judgment: UI fixes and broken behavior → Bugs; design improvements and new capabilities → Features.

After writing the file, display the full list of bugs and features as a numbered selection menu, like this:

```
Here's what's in the backlog:

🐛 Bugs
  1. <bug item>
  2. <bug item>

✨ Features / Todos
  3. <feature item>
  4. <feature item>

What would you like to work on? Pick a number or describe something else.
```

Then wait for the user to choose.
