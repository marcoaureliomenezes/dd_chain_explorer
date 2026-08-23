# tests/ — layout and CI tiers

`testpaths = ["tests", "scripts/ci/tests"]` (`pyproject.toml`) is the full pytest
surface. Run it with `pytest tests scripts/ci/tests -p no:cacheprovider` (`make test`,
and the `quality` job in `.github/workflows/plan_on_pr.yml`).

- `tests/lambda/` — both Lambda handlers (`contracts_ingestion`, `gold_to_dynamodb`),
  moto-mocked S3/DynamoDB/SSM, no network egress.
- `tests/utils/` — the kept `dm_chain_utils` modules, same moto-mocking approach.
- `tests/dabs/` — the surviving DABs job scripts' pure, import-free-of-Spark-session
  helpers.
- `scripts/ci/tests/` — static/text analysis of the Terraform/CI surface (no AWS
  credentials, no subprocess against live infrastructure).

## The pyspark tier — deliberately skipped in CI (T-R.2 F-14)

`tests/dabs/test_export_gold_location.py` imports `job_export_gold.export_gold`, which
imports `pyspark.sql` at module scope. `pytest.importorskip("pyspark", reason=...)` at
the top of that module means: if `pyspark` is not importable, the whole module is
**skipped**, not failed — the CI `quality` job does not install `pyspark` (it is a
large, JVM-backed dependency with no other consumer in this Lambda/Terraform-focused
gate), so this one file's tier is always skipped in CI today. This is a **documented,
deliberate** gap, not a silent one: AC-23's "includes tests for the DABs job scripts"
holds for the pure-helper coverage this file exercises, contingent on a developer
running it locally.

To run this tier locally: `pip install -e "utils[test-dlt]"` (declares `pyspark` as an
optional extra in `utils/pyproject.toml`, deliberately kept out of the CI-installed
`apps/lambda/requirements-dev.txt` — see that file's header comment), then
`pytest tests/dabs/test_export_gold_location.py`.
