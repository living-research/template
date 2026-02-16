# Contributing

This is a living research project. Contributions are welcome.

## How to contribute

1. **Open an issue** to discuss a question, flag a problem, or suggest an analysis.
2. **Submit a PR** with new data, experiments, or corrections.
3. **Review** existing PRs — critical feedback is as valuable as new work.

## Guidelines

- Every experiment must be reproducible via `make run` or the CI workflow.
- Raw data in `data/raw/` is immutable. Never modify source files — transform them into `data/processed/`.
- Document your reasoning in commit messages. The git history is part of the research record.
- Keep experiments self-contained. One script or notebook per analysis. Dependencies declared in `requirements.txt`.

## Attribution

All contributors are credited. Significant contributions earn co-authorship on the published findings.
