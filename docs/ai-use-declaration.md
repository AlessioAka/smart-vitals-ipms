# AI-use declaration (complete this yourself, truthfully)

The brief says inappropriate use of AI-generated content may lead to a misconduct investigation, and the
module guide says to state where and how AI was used and to be able to explain every line you submit.

This starter repository was generated with the help of an AI assistant (Claude, Anthropic) from the module
materials, the assessment brief and the project guide. Before you submit, complete and adapt this page:

- Which parts of this repository did the AI write? *(code in src/, app/, dashboard/, simulator/, tests/, notebooks, docs templates)*
- Which parts did you change, extend, or rewrite? *(list files and what you did)*
- Which parts did you write entirely yourself? *(report, design plan, ADR decisions, ethics argument, presentation?)*
- Can you explain every file? Practise: pick a file at random and explain it aloud.
- What did you check or test yourself? *(the runs and screenshots you made)*

Also check the university's current AI regulations and, if unsure, ask your tutor **before** submitting.
Signing the Canvas declaration that work is your own is your responsibility.

## Factual record of AI assistance (added by the assistant; keep it, and add your own answers above)

An AI coding assistant (Claude, Anthropic) was used in Visual Studio Code in November 2026 to:
- set up the Python environment, run the whole system, the tests and the notebooks, and find and fix bugs
  (timestamps that crashed the API, `.env` not read from the terminal, alert escalation when a sensor goes silent,
  the history limit, the demo password not updating, chart drawing, network exposure, and others);
- redesign the clinician dashboard (`dashboard/templates/`, `dashboard/views.py`);
- add drift monitoring (`src/drift.py`, `GET /model/health`) and `docs/results/first_model.md`;
- add explanatory comments and tests (`tests/test_drift.py` and new tests in other test files);
- update the README, API contract, assumptions, test plan and requirements checklist;
- write a separate explanatory Word guide for the student (not part of the submission);
- add the simulator's live mode, the always-on demo service (`deploy/`) and the chart fixes for time windows and gaps
  (`dashboard/charts.py`, `dashboard/views.py`), with their tests (`tests/test_live.py`, `tests/test_charts.py`);
- publish the repository to GitHub at the student's request;
- draft a presentation guide (speaking notes, charts and screenshots) to help the student explain the project.

The assistant did **not** write the design-plan answers, the ADR decisions, the approaches and ethics arguments
or the report. The presentation guide is a draft of speaking notes: the student must put it into their own words
and make the final slides themselves.
