# Contributing

Start with a reproducible problem and the expected behavior. Keep the change scoped: a preference from one project must not become a universal restriction.

Keep shared decisions in `SKILL.md` and detailed guidance in the relevant reference library. When updating an existing rule, clarifying when it applies is usually enough. Write contributor documentation in English; preserve language-specific examples and rules in the skill library.

After changing the library, regenerate the indexes and run all checks from the repository root with Python 3.9+:

```sh
python skills/nomoreslop-design/scripts/library.py build-index
python skills/nomoreslop-design/scripts/library.py check
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/check_repo.py
```

If skill behavior changes, repeat the affected scenario in a fresh context. Report the actual result and remaining limitations. Package checks do not assess visual quality.

Keep conversations, attachments, screenshots, third-party project sources, and raw work logs only in the ignored `.local/` directory. Receiving material in a conversation does not grant permission to publish it. Use demonstration materials only after their contents and quality have been reviewed and publication approved by the owner.

Keep the repository private until the owner has reviewed the prepared contents and explicitly authorized public access.
