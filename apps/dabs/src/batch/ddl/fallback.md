# setup_ddl.py — Limitações e Problemas de Design

## 1. `_alter`, `_table_comment`, `_apply_dlt_table_comments` não deveriam existir

Esses métodos aplicam `ALTER TABLE ... ALTER COLUMN COMMENT` e `COMMENT ON TABLE` em tabelas
**gerenciadas pelo DLT** — o script não as criou e não as possui.

**Problemas:**
- Cria dependência oculta de ordem de execução: o DLT precisa ter rodado ao menos uma vez antes
  que esses ALTERs tenham efeito. O `try/except` silencioso esconde essa falha.
- Comentários de tabelas DLT pertencem ao pipeline DLT, nos decorators `@dlt.table(comment=...)`
  e no schema `StructField(..., comment=...)`. Não num script externo.
- `_apply_dlt_table_comments` tem ~300 linhas que precisam ser mantidas em sincronia com os
  schemas dos pipelines — duplicação garantida de drift.

**Solução:** remover `_alter`, `_table_comment` e `_apply_dlt_table_comments` inteiramente.
Mover comentários para os decorators `@dlt.table` / `@dlt.view` e schemas explícitos em
`pipeline_ethereum.py` e `pipeline_app_logs.py`.

---

## 2. Abstração `_SparkExecutor` / `_WarehouseExecutor` é overengineering

O script roda como `spark_python_task` num workflow Databricks. Nesse contexto `SparkSession`
está sempre disponível via variável global `spark`. Não existe caso de produção em que não há Spark.

O modo `--warehouse-id` (Statements REST API) foi criado para contornar a ausência de cluster
no DEV Free Edition, mas:
- Adiciona ~80 linhas de HTTP polling boilerplate.
- Obriga resolução manual de host/token via env vars ou `~/.databrickscfg`.
- Ainda precisa de autenticação Databricks — não elimina nenhuma dependência real.

**Solução:** usar apenas `spark.sql()`. No DEV Free Edition, Serverless disponibiliza Spark
sem cluster dedicado — o `spark_python_task` funciona normalmente.

---

## 3. `_apply_rls` com `try/except` silencioso é falha silenciosa mascarada

`setup_all` chama `_apply_rls`, que tenta `ALTER TABLE ... SET ROW FILTER` em Materialized Views
DLT que podem não existir ainda. O `try/except` captura o erro e loga apenas um warning.

Resultado: o script termina com sucesso mesmo sem ter aplicado a segurança que deveria aplicar.
Isso não é idempotência — é falha silenciosa.

**Solução:** RLS em Materialized Views DLT deve ser aplicada num passo separado e explícito,
executado **após** o primeiro run dos pipelines DLT. Não deve estar no setup DDL inicial.

---

## 4. `drop_all` limpa schemas mas não os dados das tabelas EXTERNAL

`DROP SCHEMA CASCADE` remove os metadados do Unity Catalog, mas os arquivos Delta continuam
em S3:
- `s3://{bucket}/b_ethereum/popular_contracts_txs/`
- `s3://{bucket}/s_apps/transactions_batch/`

Um drop completo precisa remover os dados antes de dropar o schema.

**Solução:** chamar `dbutils.fs.rm(location, recurse=True)` para cada LOCATION de tabela
EXTERNAL imediatamente antes do `DROP SCHEMA CASCADE`.

---

## 5. `--comments-only` é flag que não deveria existir

Existe exclusivamente para servir `_apply_dlt_table_comments`. Ao remover o item 1, essa
flag desaparece junto.

---

## Resumo — O que o script deveria fazer

```
setup_ddl.py
  ├── CREATE SCHEMA IF NOT EXISTS  (todos os schemas)
  ├── CREATE TABLE IF NOT EXISTS   (só tabelas EXTERNAL, com comentários inline no DDL)
  │     ├── b_ethereum.popular_contracts_txs
  │     └── s_apps.transactions_batch
  └── drop_all()
        ├── dbutils.fs.rm(location, recurse=True)  ← para cada LOCATION EXTERNAL
        └── DROP SCHEMA IF EXISTS ... CASCADE
```

Nada mais. Simples, curto, preciso, claro.
