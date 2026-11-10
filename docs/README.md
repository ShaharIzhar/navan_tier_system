# Docs

Start with the [main README](../README.md). These pages hold the detail behind it.

| If you want to know… | Read |
|---|---|
| How the system decides: flowchart and every rule | [`business_logic.md`](business_logic.md) |
| What happened on real companies, with sources | [`cases.md`](cases.md) |
| How the AI prompt was tested and improved | [`llm_experiments/`](llm_experiments/README.md) |
| How accuracy would be measured | [`evaluation.md`](evaluation.md) |
| How to change a prompt or refresh the demo data | [`developer_guide.md`](developer_guide.md) |

`llm_experiments/` also holds the evidence for the prompt story: `runs/` has the raw, unedited AI answers
for each prompt version, and `prompts/` has the earlier prompt versions. The app doesn't read either folder.
