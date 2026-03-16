###############################################################################
# terraform_dev/3_iam/iam.tf
#
# IAM role que o Databricks assume para acessar o S3.
# Usa Instance Profile pattern recomendado pela Databricks para Unity Catalog.
#
# Fluxo:
#   1. Cria a IAM role com trust para o Unity Catalog IAM ARN do Databricks
#   2. A role tem permissão de leitura/escrita no bucket de ingestão DEV
#   3. O ARN da role é usado em 1_databricks/ como storage credential
###############################################################################

# ── Trust policy: permite que o Unity Catalog do Databricks assuma esta role ─

data "aws_iam_policy_document" "databricks_assume_role" {
  # Unity Catalog assume role (standard Databricks UC trust)
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [var.databricks_unity_catalog_iam_arn]
    }

    # External ID retornado pela storage credential — previne confused deputy
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.storage_credential_external_id]
    }
  }

  # Self-assume — necessário para Unity Catalog external location
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.aws_account_id}:role/dm-databricks-dev-s3-role"]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.storage_credential_external_id]
    }
  }
}

# ── IAM Role ─────────────────────────────────────────────────────────────────

resource "aws_iam_role" "databricks_s3" {
  name               = "dm-databricks-dev-s3-role"
  description        = "Role para o Databricks Free Edition acessar o S3 DEV (Unity Catalog external location)"
  assume_role_policy = data.aws_iam_policy_document.databricks_assume_role.json

  tags = { Name = "dm-databricks-dev-s3-role" }
}

# ── S3 Access Policy ──────────────────────────────────────────────────────────

data "aws_iam_policy_document" "s3_access" {
  # Leitura e escrita no bucket de ingestão
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObjectAttributes",
    ]
    resources = [
      "${local.bucket_arn}/*",
    ]
  }

  # Listagem do bucket
  statement {
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [local.bucket_arn]
  }
}

resource "aws_iam_role_policy" "s3_access" {
  name   = "dm-databricks-dev-s3-policy"
  role   = aws_iam_role.databricks_s3.id
  policy = data.aws_iam_policy_document.s3_access.json
}
