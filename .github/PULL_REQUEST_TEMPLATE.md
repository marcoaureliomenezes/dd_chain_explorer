## Description

<!-- Describe your changes clearly. What problem does this PR solve? -->

## Type of Change

- [ ] `feat` – New feature
- [ ] `fix` – Bug fix
- [ ] `chore` – Maintenance / dependency update
- [ ] `infra` – Infrastructure / Terraform change
- [ ] `ci` – CI/CD pipeline change
- [ ] `docs` – Documentation only

## Changes Made

<!-- List the key files/components changed and why -->

-

## Testing

- [ ] Unit tests pass (`pytest dd_chain_explorer/utils/tests/unit/ -v`)
- [ ] Docker Compose validates locally (`docker compose -f services/dev/compose/app_services.yml config`)
- [ ] DEV environment tested (if applicable)
- [ ] Terraform plan reviewed (if infra changes included)

## Checklist

- [ ] PR targets the correct branch (`develop` for features, `main` for releases only)
- [ ] Commit messages follow conventional format (`feat:`, `fix:`, `chore:`, etc.)
- [ ] No secrets or credentials are hardcoded
- [ ] New imports use `dm_chain_utils.*` (not `utils.*` or `dm_33_utils.*`)
- [ ] Documentation updated (if applicable)

## Breaking Changes

- [ ] This PR introduces breaking changes

<!-- If yes, describe the impact and migration steps: -->

## Related Issues / PRs

<!-- Closes #123 -->
