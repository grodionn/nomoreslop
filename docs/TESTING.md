# Testing

From the repository root, with Python 3.10+:

```sh
python skills/nomoreslop-design/scripts/library.py build-index
python skills/nomoreslop-design/scripts/library.py check
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest discover -s skills/nomoreslop-design/tests -p "test_*.py" -v
python scripts/check_repo.py
python -m unittest discover -s skills/nomoreslop-typography/tests -p "test_*.py" -v
python -m unittest discover -s skills/nomoreslop-color/tests -p "test_*.py" -v
```

These commands check library integrity, CLI behavior, installation portability, distribution paths, local documentation links, resource selection, project-state validation, and text inventory. Core checks require no third-party packages. Binary font tests use optional fontTools when available; dependency-specific tests can be skipped without it. WOFF2 inspection may also require brotli. No dependencies are installed automatically. CI runs checks on Linux with Python 3.10 and 3.13, and on Windows with Python 3.13.

Behavior scenarios require separate runs. Give the agent the prompt and prepared materials; keep expectations with the evaluator. A written scenario is not a completed test. The following scenario documents are currently in Russian:

- [Design](../skills/nomoreslop-design/checks/scenarios.md): briefing, composition, visual choices, and review.
- [Writing](../skills/nomoreslop-writing/checks/scenarios.md): text roles, punctuation, facts, voice, states, localization, and scope. Include good counterexamples that the skill must preserve.
- [Coordinator](../skills/nomoreslop/checks/scenarios.md): new sites, redesigns, meaningful visual questions, partial answers, delegated decisions, and sufficient existing briefs. Routing a small button edit does not cover these cases.
- [Typography](../skills/nomoreslop-typography/checks/scenarios.md): reading, spacing, identity, source selection, languages, zoom, and evidence boundaries.
- [Color](../skills/nomoreslop-color/checks/scenarios.md): source depth, scientific context, intensity, paired themes, gradients, and scope.
- [3D](../skills/nomoreslop-3d/checks/scenarios.md): subject selection, visible detail, abstraction, palette, measured load, and continuous presentation. Execution and performance require a real render and measured interaction; a good plan establishes only the decisions made. A narrow viewport does not prove smooth performance on a physical phone.

Assess copy and design against the actual artifact and task. Tool checks cannot replace that assessment. Individual runs do not demonstrate an advantage over an agent without the skills. Store run transcripts and raw logs in `.local/`; they are excluded from distribution.
