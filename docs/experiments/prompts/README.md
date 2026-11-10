# Earlier research prompts (archive)

The app sends only the live prompt in `backend/prompts/` (labelled **v4**). These files are the earlier
versions, kept as the record of how the prompt was tested and refined. Nothing in the app reads them.

| Version | Change | Why |
|---|---|---|
| v1 | First version | Baseline |
| v2 | Search plan with a travel search; headcount bands stay text; fewer false conflicts | v1 turned "51-200" into 51, found no travel evidence, and flagged normal database differences as conflicts |
| v3 | Each travel finding labelled business / local field / unclear | Community-nurse home visits were read as business travel |
| v4 (live) | Standard research narrowed to 5 routing basics; travel moves to Deep Research | Cost and focus |

`manifest_history.json` is the manifest as it was with every version registered. Raw AI answers per
version are in `../v1` to `../v4`; the story is in `../../llm_experiments.md`. `backend/tests/test_prompts.py`
checks these files still reproduce the prompts sent in those saved runs.
