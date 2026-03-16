# Code quality and trackers

Short reference for SonarQube/SonarCloud and other project trackers.

## SonarQube / SonarCloud

- **Config:** `sonar-project.properties` at repo root (sources, exclusions, coverage path).
- **Coverage:** CI runs tests with `coverage run`, then `coverage xml -o coverage.xml`. Sonar reads `coverage.xml` so the dashboard shows coverage instead of "No data".
- **CI:** `.github/workflows/code-quality.yml` runs tests, generates coverage, and runs SonarCloud scan when `SONAR_TOKEN` is set in repo secrets.
- **To fix "Quality Gate failed" and "Last analysis had a warning":**
  1. Ensure `SONAR_TOKEN` is set in GitHub → Settings → Secrets so CI can send coverage and run the scanner.
  2. In SonarCloud: check the failed condition (e.g. "Coverage on New Code" or "Open Issues"). Fix new issues or adjust the Quality Gate in the project settings if the default is too strict for this repo.
  3. Exclusions in `sonar-project.properties` reduce noise (e.g. `docs/`, `schema/*.sql`); adjust if you want them analyzed.
- **Local:** Run tests with coverage: `pip install -r requirements-dev.txt`, then `PYTHONPATH=. coverage run -m unittest discover -s tests -p "test_*.py"` and `coverage xml -o coverage.xml`. Run the Sonar scanner locally if you have it configured.

## Other trackers

- **Linear:** Canonical backlog; use for EPICs and task status.
- **GitHub Projects:** Execution mirror; keep in sync with Linear when closing or moving work.
- **GitHub Issues:** Linked to backlog; use templates under `.github/ISSUE_TEMPLATE/`.

No other code-quality bots or trackers are configured in-repo by default.
