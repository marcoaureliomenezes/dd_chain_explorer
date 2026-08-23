"""Guards against a repeat of the rc-1 HIGH finding: the Databricks Unity Catalog
storage-credential ExternalId (a UUID, `sensitive = true`) was committed as a
Terraform `default` in a public repo (services/dev/01_peripherals/variables.tf,
services/hml/04_peripherals/variables.tf). The fix removed both defaults — the
value is now supplied only via `TF_VAR_<name>` from the repository secret
`DATABRICKS_UC_EXTERNAL_ID`. This test fails loud if a UUID-shaped literal ever
reappears as a `default` in any `variables.tf` under `services/`.

Intent: CONTRACT — T-R.2 (rc-1 security review, HIGH finding). Hermetic; no
network, no real cloud.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES_DIR = REPO_ROOT / "services"

# RFC 4122 UUID shape (any version) — case-insensitive, matches the ExternalId
# format Databricks issues.
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# A Terraform `default = "..."` assignment, tolerant of surrounding whitespace.
DEFAULT_STRING_RE = re.compile(r'default\s*=\s*"([^"]*)"')


def _all_variables_tf() -> list[Path]:
    return sorted(SERVICES_DIR.rglob("variables.tf"))


def test_services_directory_is_present() -> None:
    # Sanity check the fixture root resolved correctly — a silently-empty glob
    # below would make every other assertion in this module vacuously true.
    assert SERVICES_DIR.is_dir()
    assert _all_variables_tf(), "no variables.tf found under services/ — path resolution broke"


def test_no_variables_tf_default_is_a_uuid() -> None:
    """No `variables.tf` under services/ may carry a UUID-shaped literal as a
    `default` — that is exactly the shape of a Databricks UC ExternalId (or any
    other opaque tenant/credential identifier) and belongs only in TF_VAR_* from
    a repository secret, never a public-repo literal default."""
    offenders: list[str] = []
    for path in _all_variables_tf():
        text = path.read_text()
        for match in DEFAULT_STRING_RE.finditer(text):
            value = match.group(1)
            if UUID_RE.fullmatch(value):
                line_no = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}")
    assert not offenders, (
        "UUID-shaped literal found as a Terraform variable default "
        f"(strip the default, supply via TF_VAR_<name> from a repo secret): {offenders}"
    )


def test_uc_external_id_variables_carry_no_default() -> None:
    """Named regression guard for the exact rc-1 finding: both ExternalId
    variables must declare `sensitive = true` and no `default` at all."""
    targets = {
        SERVICES_DIR / "dev" / "01_peripherals" / "variables.tf": "databricks_dev_uc_external_id",
        SERVICES_DIR / "hml" / "04_peripherals" / "variables.tf": "databricks_hml_uc_external_id",
    }
    for path, var_name in targets.items():
        assert path.is_file(), f"expected stack file missing: {path}"
        text = path.read_text()
        block_match = re.search(
            r'variable\s+"' + re.escape(var_name) + r'"\s*\{([^}]*)\}', text, re.DOTALL
        )
        assert block_match, f"variable {var_name!r} not found in {path}"
        block = block_match.group(1)
        assert "default" not in block, f"{path}: {var_name!r} must not declare a default"
        assert re.search(r"sensitive\s*=\s*true", block), (
            f"{path}: {var_name!r} must declare sensitive = true"
        )
