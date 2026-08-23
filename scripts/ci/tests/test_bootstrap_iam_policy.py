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
    text = _read("policies.tf")
    documents = _policy_document_blocks(text)
    assert documents, "expected at least one aws_iam_policy_document in policies.tf"

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
    assert len(deny_statements) == 2, "expected exactly 2 Deny statements"

    iam_star_deny = next(s for s in deny_statements if '"iam:*"' in s)
    assert "dm-chain-explorer-gha-*" in iam_star_deny

    cred_deny = next(s for s in deny_statements if "CreateAccessKey" in s)
    for action in ("iam:CreateAccessKey", "iam:AttachUserPolicy", "iam:PutUserPolicy"):
        assert action in cred_deny


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
