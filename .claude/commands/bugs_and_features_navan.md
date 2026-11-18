Read the Apple Note titled "bugs and feature navan" using the Apple Notes MCP tool (`get_note_content` with note_name: "bugs and feature navan").

If the note can't be found or read, say so and stop. Do not write or overwrite the file.

**Only include open (unchecked) items — skip any items that are checked off/completed.**

Classify each open item into one of two categories:
- **Bugs**: Issues, broken behavior, UI glitches, things that are malfunctioning or not working as expected.
- **Features / Todos**: Enhancements, improvements, design requests, or new functionality to add.

Then fully overwrite the file at:
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
