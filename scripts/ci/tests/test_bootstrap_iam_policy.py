"""Static least-privilege proof for services/prd/00_bootstrap's IAM policies.

Intent: CONTRACT — AC-2 / AC-2b (T-A.3b). Complements, but does not replace, the
live negative proof the coordinator runs post-apply
(`aws iam simulate-principal-policy` against each `gha` role, T-A.3), which needs
real AWS credentials this suite never has. What is provable without touching AWS
is provable here, deterministically, from the checked-in HCL source: every
`Allow` statement's `resources` list is built only from the project-prefix
locals (or the state bucket / lock table / artifacts bucket) declared in
`locals.tf` — never a bare `"*"` and never an unscoped identifier — and the
explicit self-mutation `Deny` is attached to all four `gha` roles.
Size: unit (pure text/static analysis, no subprocess, no network).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOTSTRAP_DIR = REPO_ROOT / "services" / "prd" / "00_bootstrap"
SERVICES_DIR = REPO_ROOT / "services"

# Every local.tf identifier that is provably scoped to a project resource
# prefix, the terraform state bucket, the state lock table, or the artifacts
# bucket — i.e. everything a `resources = [...]` value is allowed to reference
# in an Allow statement. Kept in lockstep with locals.tf by hand: a new
# resource-type local must be added here before this test admits it.
ALLOWED_RESOURCE_LOCALS = {
    "s3_bucket_arns",
    "dynamodb_table_arns",
    "lambda_function_arns",
    "lambda_layer_arns",
    "log_group_arns",
    "events_rule_arns",
    "iam_role_arns",
    "iam_instance_profile_arns",
    "iam_policy_arns",
    "ssm_parameter_arns",
    "artifacts_bucket_arn",
    "artifacts_layer_prefix_rw",
    "tf_state_bucket_arn",
    "tf_state_objects_arn",
    "tf_lock_table_arn",
}


def _read(name: str) -> str:
    return (BOOTSTRAP_DIR / name).read_text()


def _split_top_level_blocks(text: str, opener: str) -> list[str]:
    """Return the full text of every `<opener> { ... }` block, brace-balanced."""
    blocks = []
    for m in re.finditer(re.escape(opener) + r"\s*\{", text):
        depth = 1
        i = m.end()
        while depth and i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        blocks.append(text[m.start() : i])
    return blocks


def _statement_blocks(policy_doc_text: str) -> list[str]:
    return _split_top_level_blocks(policy_doc_text, "statement")


def _policy_document_blocks(text: str) -> dict[str, str]:
    """Map policy-document local name -> its full block text."""
    out: dict[str, str] = {}
    for m in re.finditer(
        r'data\s+"aws_iam_policy_document"\s+"(\w+)"\s*\{', text
    ):
        depth = 1
        i = m.end()
        while depth and i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        out[m.group(1)] = text[m.start() : i]
    return out


def _resources_value(statement_text: str) -> str | None:
    m = re.search(r"resources\s*=\s*(.+?)\n(\s*\})", statement_text, re.S)
    if not m:
        return None
    return m.group(1).strip()


def _effect(statement_text: str) -> str:
    m = re.search(r'effect\s*=\s*"(\w+)"', statement_text)
    return m.group(1) if m else "Allow"  # AWS default when omitted


def test_every_allow_statement_resource_is_project_scoped() -> None:
    documents: dict[str, str] = {}
    for filename in ("policies.tf", "boundary.tf"):
        documents.update(_policy_document_blocks(_read(filename)))
    assert documents, "expected at least one aws_iam_policy_document"

    violations: list[str] = []
    for doc_name, doc_text in documents.items():
        for stmt in _statement_blocks(doc_text):
            if _effect(stmt) != "Allow":
                continue
            resources = _resources_value(stmt)
            sid_match = re.search(r'sid\s*=\s*"(\w+)"', stmt)
            sid = sid_match.group(1) if sid_match else "<no-sid>"
            if resources is None:
                violations.append(f"{doc_name}.{sid}: no resources attribute")
                continue
            if '"*"' in resources or resources.strip() == "*":
                violations.append(f"{doc_name}.{sid}: resources includes literal \"*\"")
                continue
            referenced_locals = set(re.findall(r"local\.(\w+)", resources))
            unscoped = referenced_locals - ALLOWED_RESOURCE_LOCALS
            if not referenced_locals:
                violations.append(
                    f"{doc_name}.{sid}: resources references no known local — "
                    f"got {resources!r}"
                )
            elif unscoped:
                violations.append(
                    f"{doc_name}.{sid}: resources references un-scoped local(s) "
                    f"{sorted(unscoped)} — got {resources!r}"
                )

    assert not violations, "Allow statement(s) not provably project-scoped:\n" + "\n".join(
        violations
    )


def test_self_mutation_deny_covers_iam_star_and_user_credential_verbs() -> None:
    text = _read("policies.tf")
    documents = _policy_document_blocks(text)
    deny_doc = documents["gha_self_mutation_deny"]
    statements = _statement_blocks(deny_doc)
    deny_statements = [s for s in statements if _effect(s) == "Deny"]
    # T-A.2 hardening (2026-08-23T164159Z REJECTED verdict) added 3 Deny
    # statements to the original 2: state-backend destructive actions,
    # lock-table destructive actions, project-bucket public-exposure
    # actions, plus a 6th closing the permissions-boundary tamper path.
    assert len(deny_statements) == 6, "expected exactly 6 Deny statements"

    iam_star_deny = next(s for s in deny_statements if '"iam:*"' in s)
    assert "dm-chain-explorer-gha-*" in iam_star_deny

    cred_deny = next(s for s in deny_statements if "CreateAccessKey" in s)
    for action in ("iam:CreateAccessKey", "iam:AttachUserPolicy", "iam:PutUserPolicy"):
        assert action in cred_deny

    state_backend_deny = next(s for s in deny_statements if "DenyStateBackendDestructiveActions" in s)
    for action in (
        "s3:DeleteBucket",
        "s3:PutBucketVersioning",
        "s3:DeleteObjectVersion",
        "s3:PutBucketPolicy",
        # T-A.2 rev2 LOW residuals.
        "s3:DeleteBucketPolicy",
        "s3:PutBucketLogging",
        "s3:PutBucketOwnershipControls",
    ):
        assert action in state_backend_deny
    for local_name in ("tf_state_bucket_arn", "tf_state_objects_arn", "artifacts_bucket_arn"):
        assert f"local.{local_name}" in state_backend_deny

    lock_table_deny = next(s for s in deny_statements if "DenyStateLockTableDestructiveActions" in s)
    assert "dynamodb:DeleteTable" in lock_table_deny
    assert "dynamodb:UpdateTable" in lock_table_deny
    assert "local.tf_lock_table_arn" in lock_table_deny

    public_exposure_deny = next(s for s in deny_statements if "DenyProjectBucketPublicExposure" in s)
    for action in (
        "s3:PutBucketAcl",
        "s3:PutBucketPublicAccessBlock",
        "s3:PutBucketPolicy",
        # T-A.2 rev2 LOW residuals.
        "s3:DeleteBucketPolicy",
        "s3:PutObjectAcl",
    ):
        assert action in public_exposure_deny
    assert "local.s3_bucket_arns" in public_exposure_deny

    # T-A.2 rev2 HIGH (remaining blocker) — the Deny now covers ONLY
    # DeleteRolePermissionsBoundary. iam:PutRolePermissionsBoundary is
    # deliberately NOT denied here: it is the sole retrofit path onto the 8
    # pre-existing project roles, permitted only conditionally by the
    # ProjectIamRoleSetBoundary Allow (asserted separately below).
    boundary_tamper_deny = next(
        s for s in deny_statements if "DenyRolePermissionsBoundaryTampering" in s
    )
    assert "iam:DeleteRolePermissionsBoundary" in boundary_tamper_deny
    assert "iam:PutRolePermissionsBoundary" not in boundary_tamper_deny


def test_no_catch_all_dm_prefix() -> None:
    """T-A.2 HIGH #1 — the 2-character 'dm-' prefix subsumed the other 3
    project prefixes and widened every Allow to the whole shared account's
    dm-* namespace. Only the 3 full project-name prefixes may remain."""
    text = _read("variables.tf")
    m = re.search(r'variable "project_name_prefixes" \{.*?default\s*=\s*(\[[^\]]*\])', text, re.S)
    assert m, "project_name_prefixes default not found"
    default_value = m.group(1)
    assert '"dm-"' not in default_value, f"catch-all 'dm-' prefix still present: {default_value}"
    for prefix in ('"dm-chain-explorer-"', '"dm-dd-chain-explorer-"', '"dm-databricks-"'):
        assert prefix in default_value


def test_create_role_requires_permissions_boundary() -> None:
    """T-A.2 HIGH #3 — iam:CreateRole must be its own statement, conditioned
    on the ci_boundary permissions boundary, and absent from the broader
    role-management statement (which has no such condition)."""
    text = _read("policies.tf")
    documents = _policy_document_blocks(text)
    deploy_doc = documents["gha_deploy_permissions"]
    statements = _statement_blocks(deploy_doc)

    create_stmt = next(s for s in statements if "ProjectIamRoleCreate" in s)
    assert '"iam:CreateRole"' in create_stmt
    assert "iam:PermissionsBoundary" in create_stmt
    assert "aws_iam_policy.ci_boundary.arn" in create_stmt

    mgmt_stmt = next(s for s in statements if "ProjectIamRoleManagement" in s)
    assert '"iam:CreateRole"' not in mgmt_stmt
    assert "iam:UpdateAssumeRolePolicy" in mgmt_stmt


def test_set_permissions_boundary_is_conditioned_on_ci_boundary() -> None:
    """T-A.2 rev2 HIGH (remaining blocker) — the retrofit-onto-existing-role
    path: iam:PutRolePermissionsBoundary must be its own statement,
    conditioned on the same ci_boundary ARN as CreateRole, so a deploy role
    can only ever SET ci_boundary and never a weaker/attacker-chosen one."""
    text = _read("policies.tf")
    documents = _policy_document_blocks(text)
    deploy_doc = documents["gha_deploy_permissions"]
    statements = _statement_blocks(deploy_doc)

    set_boundary_stmt = next(s for s in statements if "ProjectIamRoleSetBoundary" in s)
    assert '"iam:PutRolePermissionsBoundary"' in set_boundary_stmt
    assert "iam:PermissionsBoundary" in set_boundary_stmt
    assert "aws_iam_policy.ci_boundary.arn" in set_boundary_stmt
    assert "local.iam_role_arns" in set_boundary_stmt


def test_pass_role_requires_passed_to_service_condition() -> None:
    """T-A.2 HIGH #3 — iam:PassRole must be conditioned on iam:PassedToService
    naming only the AWS services this project actually passes a role to."""
    text = _read("policies.tf")
    documents = _policy_document_blocks(text)
    deploy_doc = documents["gha_deploy_permissions"]
    pass_role_stmt = next(
        s for s in _statement_blocks(deploy_doc) if "ProjectIamPassRole" in s
    )
    assert "iam:PassedToService" in pass_role_stmt
    assert "lambda.amazonaws.com" in pass_role_stmt
    assert "events.amazonaws.com" in pass_role_stmt


def test_ci_boundary_grants_no_iam_action() -> None:
    """T-A.2 HIGH #3 — the boundary itself must grant zero iam:* actions, so a
    role created under it can never manage IAM regardless of its own inline
    policy."""
    text = _read("boundary.tf")
    documents = _policy_document_blocks(text)
    boundary_doc = documents["ci_boundary"]
    for stmt in _statement_blocks(boundary_doc):
        if _effect(stmt) != "Allow":
            continue
        assert '"iam:' not in stmt, f"boundary Allow statement grants an iam: action: {stmt}"


def test_all_four_gha_roles_attach_the_self_mutation_deny() -> None:
    text = _read("iam.tf")
    role_names = {
        "gha_deploy_dev",
        "gha_deploy_hml",
        "gha_deploy_prd",
        "gha_readonly_plan",
    }
    for role in role_names:
        pattern = (
            rf'resource\s+"aws_iam_role_policy"\s+"{role}_deny"\s*\{{[^}}]*'
            rf"role\s*=\s*aws_iam_role\.{role}\.id[^}}]*"
            r"policy\s*=\s*data\.aws_iam_policy_document\.gha_self_mutation_deny\.json"
        )
        assert re.search(pattern, text), f"{role} does not attach gha_self_mutation_deny"


def test_readonly_plan_role_grants_no_lock_table_write() -> None:
    text = _read("policies.tf")
    documents = _policy_document_blocks(text)
    readonly_doc = documents["gha_readonly_plan_permissions"]
    assert "dynamodb:PutItem" not in readonly_doc
    assert "dynamodb:DeleteItem" not in readonly_doc
    assert "tf_lock_table_arn" not in readonly_doc


def test_deploy_permissions_grant_lock_table_read_and_write() -> None:
    text = _read("policies.tf")
    documents = _policy_document_blocks(text)
    deploy_doc = documents["gha_deploy_permissions"]
    assert "local.tf_lock_table_arn" in deploy_doc
    assert "dynamodb:PutItem" in deploy_doc
    assert "dynamodb:DeleteItem" in deploy_doc


def _iam_role_blocks_outside_bootstrap() -> list[tuple[Path, str, str]]:
    """(file, role_label, block_text) for every `aws_iam_role` resource under
    services/ that is NOT one of the 4 `gha_*` roles 00_bootstrap itself
    creates — those are the boundary's creators, not project roles bound by
    it. Returns every project role the T-A.2 rev2 HIGH retrofit covers."""
    results: list[tuple[Path, str, str]] = []
    for tf_file in sorted(SERVICES_DIR.rglob("*.tf")):
        if BOOTSTRAP_DIR in tf_file.parents:
            continue
        text = tf_file.read_text()
        for m in re.finditer(r'resource\s+"aws_iam_role"\s+"(\w+)"\s*\{', text):
            depth = 1
            i = m.end()
            while depth and i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
            block = text[m.start() : i]
            results.append((tf_file, m.group(1), block))
    return results


def test_every_project_iam_role_sets_permissions_boundary() -> None:
    """T-A.2 rev2 HIGH (remaining blocker) — the permissions boundary must
    be retrofitted onto every project `aws_iam_role`, not only the ones the
    bootstrap stack creates going forward. A role missing
    `permissions_boundary` reopens the CreateRole/PassRole escalation chain
    the boundary exists to close."""
    role_blocks = _iam_role_blocks_outside_bootstrap()
    assert role_blocks, "expected at least one project aws_iam_role under services/"
    # Locks the exact count from the T-A.2 rev2 verdict's file:line list so a
    # newly-added project role cannot silently reopen the gap unnoticed.
    assert len(role_blocks) == 8, (
        f"expected exactly 8 project aws_iam_role resources outside "
        f"00_bootstrap, found {len(role_blocks)}: "
        f"{[(str(f.relative_to(REPO_ROOT)), name) for f, name, _ in role_blocks]}"
    )

    violations = [
        f"{tf_file.relative_to(REPO_ROOT)}:{role_name}"
        for tf_file, role_name, block in role_blocks
        if "permissions_boundary" not in block
    ]
    assert not violations, (
        "project aws_iam_role resource(s) with no permissions_boundary:\n"
        + "\n".join(violations)
    )


def test_no_managed_policy_attachment_in_bootstrap_stack() -> None:
    for filename in ("iam.tf", "policies.tf"):
        text = _read(filename)
        assert "aws_iam_role_policy_attachment" not in text, (
            f"{filename} attaches a managed policy — 00_bootstrap must use only "
            "inline aws_iam_role_policy statements (D14)"
        )
        assert "PowerUserAccess" not in text
        assert "AdministratorAccess" not in text
        assert "ReadOnlyAccess" not in text
