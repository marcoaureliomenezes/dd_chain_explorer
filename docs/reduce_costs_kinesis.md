# Análise de Custos Kinesis — dd_chain_explorer

> Gerado em: 2026-03-24  
> Status: **Fase 1 concluída** (Option A implementada no commit `7128448`)

---

## 1. Contexto

O projeto `dd_chain_explorer` utiliza Amazon Kinesis Data Streams como backbone de mensageria entre os jobs de captura on-chain (Docker ECS) e o pipeline de processamento (Databricks DLT). São 3 streams:

```
Job3 (block_data_crawler)   ──▶  mainnet-blocks-data          ──▶  Firehose ──▶ S3
                                                                 ▲
Job4 (mined_txs_crawler)    ──▶  mainnet-transactions-data    ──┤  Firehose ──▶ S3
                                                                 ▼
Job5 (txs_input_decoder)    ◀──  mainnet-transactions-data
Job5 (txs_input_decoder)    ──▶  mainnet-transactions-decoded ──▶  Firehose ──▶ S3
```

**Produtores por stream:**

| Stream | Produtor único | Consumidores |
|--------|---------------|--------------|
| `mainnet-blocks-data` | Job3 | Firehose apenas |
| `mainnet-transactions-data` | Job4 | Job5 + Firehose |
| `mainnet-transactions-decoded` | Job5 | Firehose apenas |

---

## 2. Diagnóstico de Custo — Situação Anterior

### Período analisado: 19–23 Mar 2026 (5 dias)
- **Custo total Kinesis DEV**: $41.83 MTD

### Causa raiz

O modo `ON_DEMAND` do Kinesis mantém automaticamente, no mínimo, 4 shards — escalando conforme o pico histórico mas nunca descendo abaixo de 4. Com 3 streams em ON_DEMAND:

```
4 shards × 3 streams × 24h × $0.021/shard-hr = $6.05/dia (baseline mínimo)
```

Com o tráfego atual do DEV, o ON_DEMAND nunca escala além de 4 shards, tornando o modo ainda mais ineficiente — paga-se sempre pelo piso mínimo sem usufruir da elasticidade.

### Throughput real vs capacidade

| Stream | Throughput estimado | Capacidade 1 shard | % utilizado |
|--------|--------------------|--------------------|:-----------:|
| `mainnet-blocks-data` | ~5 KB/s | 1 MB/s | **0.5%** |
| `mainnet-transactions-data` | ~51 KB/s | 1 MB/s | **5.1%** |
| `mainnet-transactions-decoded` | ~18 KB/s | 1 MB/s | **1.8%** |

Todos os streams operam em < 6% da capacidade de um único shard — justificando a mudança para PROVISIONED com `shard_count = 1`.

---

## 3. Opções de Otimização

### Comparação geral

| Opção | Descrição | Streams KDS | Custo/dia | Economia mês | Complexidade |
|-------|-----------|:-----------:|----------:|-------------:|:------------:|
| **Atual** (antes) | 3 ON_DEMAND (4+ shards cada) | 3 | $8–12 | — | — |
| **A** ✅ | PROVISIONED 1 shard | 3 | ~$1.80 | ~$190–300 | ⭐ mínima |
| **A+B+C** | A + Firehose Direct para blocks e decoded | 1 | ~$0.55 | ~$220–340 | ⭐⭐ baixa |
| **D** ❌ | 1 stream multiplexada | 1 | ~$0.50 | similar | ⭐⭐⭐⭐ alta |

---

### Option A — ON_DEMAND → PROVISIONED 1 shard ✅ IMPLEMENTADA

**Princípio:** Substituir o modo elástico pelo modo fixo com 1 shard por stream.

**Custo estimado pós-mudança:**
```
1 shard × 3 streams × 24h × $0.021/shard-hr ≈ $1.51/dia
+ PUT payload units (~$0.30/dia estimado com throughput atual)
Total ≈ $1.80/dia
```

**Economia:** ~80–85% de redução vs ON_DEMAND.

**Arquivos modificados (commit `7128448`):**

| Arquivo | Mudança |
|---------|---------|
| `services/dev/01_peripherals/main.tf` | `stream_mode = "PROVISIONED"`, `shard_count = 1` |
| `services/hml/04_peripherals/main.tf` | idem |
| `services/prd/04_peripherals/peripherals.tf` | idem |

**Risco:** Se o throughput de `mainnet-transactions-data` ultrapassar 1 MB/s (improvável no cenário atual), ocorrerá `ProvisionedThroughputExceededException`. Monitorar via CloudWatch `WriteProvisionedThroughputExceeded`.

---

### Option B+C — Firehose Direct para `blocks-data` e `transactions-decoded`

**Princípio:** Os streams `mainnet-blocks-data` e `mainnet-transactions-decoded` têm apenas **1 consumidor cada: o Firehose**. Não há necessidade de um stream KDS como intermediário — os produtores (Job3 e Job5) podem gravar diretamente no Firehose, eliminando 2 dos 3 streams KDS.

```
Antes:  Job3 → KDS(blocks-data) → Firehose → S3
Depois: Job3 ──────────────────→ Firehose → S3

Antes:  Job5 → KDS(transactions-decoded) → Firehose → S3
Depois: Job5 ──────────────────────────→ Firehose → S3
```

**Resultado:** Apenas 1 stream KDS permanece (`mainnet-transactions-data`), usado pelo Job5 como consumidor.

**Custo estimado (A+B+C):**
```
1 shard × 1 stream × 24h × $0.021/shard-hr ≈ $0.50/dia
+ PUT payload Firehose direto (~$0.05/dia por stream extra)
Total ≈ $0.55/dia
```

**Arquivos a modificar para Phase 2:**

| Arquivo | Mudança necessária |
|---------|-------------------|
| `utils/src/dm_chain_utils/dm_kinesis.py` | Base de referência — criar `dm_firehose.py` análogo |
| `utils/src/dm_chain_utils/dm_firehose.py` | **NOVO** — `FirehoseHandler` com `put_record()` / `put_records()` equivalentes |
| `apps/docker/onchain-stream-txs/src/3_block_data_crawler.py` | Alterar `sink_config`/`run()` para usar `FirehoseHandler` em vez de `KinesisHandler` |
| `apps/docker/onchain-stream-txs/src/5_txs_input_decoder.py` | Alterar output stream (já lê de KDS, mas escreve via FirehoseHandler) |
| `services/dev/01_peripherals/main.tf` | Remover `blocks-data` e `transactions-decoded` do mapa de KDS streams; adicionar recursos Firehose standalone |
| `services/hml/04_peripherals/main.tf` | idem |
| `services/prd/04_peripherals/peripherals.tf` | idem |

**Notas de implementação:**
- A API do Firehose direto usa `put_record(DeliveryStreamName=..., Record={"Data": ...})` em vez de `put_records(StreamName=..., Records=[...])`
- O Firehose aceita payloads de até 1.000 KB por record e até 500 records por `put_record_batch`
- O buffering do Firehose (padrão: 5 MB / 5 min) introduz latência na chegada ao S3 — aceitável para batch/DLT, não para real-time

---

### Option D — Stream KDS único multiplexado ❌ NÃO RECOMENDADA

**Princípio:** Unificar os 3 streams em 1, adicionando campo `type` no payload para demultiplexar no consumidor.

**Por que NÃO fazer:**

1. **Feedback loop no Job5**: Job5 lê de `transactions-data` e escreve no mesmo stream multiplexado → Job5 consumiria suas próprias mensagens (loop infinito) sem lógica de filtragem por `type`.
2. **Custo de leitura triplicado**: O Job5 leria blocos + transações + decoded para filtrar apenas `transactions-data` — 3× o volume de leitura atual.
3. **Conflito de schema no DLT Auto Loader**: O Firehose escreveria payloads heterogêneos no S3 → o Auto Loader do Databricks teria dificuldade em inferir schema.
4. **Acoplamento de jobs**: Uma mudança de schema em um stream afeta todos os consumidores do stream unificado.

---

## 4. Plano de Execução

### Fase 1 — ✅ CONCLUÍDA (commit `7128448`)

- [x] Alterar todos os 3 streams em dev/hml/prd para `PROVISIONED`, `shard_count = 1`
- [x] Destruir infra DEV (run CI `23521469179`)
- [x] Re-provisionar DEV com novas configurações (run CI `23522090850`)

**Economia esperada Fase 1:** ~$6–10/dia → ~$1.50/dia (~80% redução)

### Fase 2 — PENDENTE (Option B+C: Firehose Direct)

Pré-requisito: Validar estabilidade da Fase 1 por pelo menos 1 sprint.

1. Implementar `utils/src/dm_chain_utils/dm_firehose.py`
2. Adaptar Job3 e Job5 para escrever diretamente no Firehose
3. Atualizar Terraform (remover 2 streams KDS, adicionar Firehose resources standalone nos 3 envs)
4. Deploy em DEV → validar via integration tests
5. Deploy em HML → validar
6. Deploy em PRD

**Economia adicional esperada Fase 2:** ~$1.25/dia adicionais (~70% sobre Fase 1)

---

## 5. Monitoramento Pós-Fase 1

### CloudWatch alarms recomendados por stream (`mainnet-transactions-data-dev`):

```hcl
# WriteProvisionedThroughputExceeded > 0 em qualquer período de 5 min
# GetRecords.IteratorAgeMilliseconds > 60000 (lag > 1 min)
# PutRecord.Success < 99% (erros de gravação)
```

### Verificação manual pós-deploy:

```bash
for s in mainnet-blocks-data mainnet-transactions-data mainnet-transactions-decoded; do
  aws kinesis describe-stream-summary \
    --stream-name "${s}-dev" \
    --region sa-east-1 \
    --query 'StreamDescriptionSummary.{Name:StreamName,Mode:StreamModeDetails.StreamMode,Shards:OpenShardCount}' \
    --output table
done
# Esperado: Mode=PROVISIONED, Shards=1 para todos
```

---

## 6. Referências

- `services/dev/01_peripherals/main.tf` — configuração KDS DEV
- `services/hml/04_peripherals/main.tf` — configuração KDS HML
- `services/prd/04_peripherals/peripherals.tf` — configuração KDS PRD
- `utils/src/dm_chain_utils/dm_kinesis.py` — KinesisHandler atual
- `apps/docker/onchain-stream-txs/src/3_block_data_crawler.py` — Job3 (produtor blocks-data)
- `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py` — Job4 (produtor transactions-data)
- `apps/docker/onchain-stream-txs/src/5_txs_input_decoder.py` — Job5 (consumidor + produtor transactions-decoded)
- `docs/report_finops.md` — relatório de custos AWS 2026-03-24
