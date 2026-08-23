# docs/

Operator runbooks that don't belong in `specs/` (which is the SDD source of
truth for product/architecture/task state — see `specs/AGENTS.md`) or in a
component-level `README.md`.

## Contents

- [`runbooks/00-bootstrap-apply.md`](runbooks/00-bootstrap-apply.md) — the
  one-time, operator-only apply of `services/prd/00_bootstrap` (the OIDC
  roles CI authenticates as). Read before ever running `make prd_bootstrap_apply`.

## Where everything else lives

| Question | Where |
|---|---|
| What is this release changing, and why | `specs/releases/<active-id>/SPEC.md` |
| Current product/architecture/tech-stack truth | `specs/memory/*.md` |
| Repo-wide agent operating rules | `AGENTS.md` (repo root) |
| Lambda function details | `apps/lambda/README.md` |
| Shared library details | `utils/README.md` |
| Databricks bundle details | `apps/dabs/README.md` |
| Make targets | `make help`, or the `Makefile` itself |
