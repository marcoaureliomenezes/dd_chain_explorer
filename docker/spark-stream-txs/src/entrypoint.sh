#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# entrypoint.sh — submete um job PySpark ao cluster Spark.
#
# Todos os JARs (Kafka, Avro, Hadoop-AWS) já estão pré-instalados na imagem
# Docker (ver Dockerfile). Não é necessário --packages em runtime.
# ─────────────────────────────────────────────────────────────────────────────

PYSPARK_SCRIPT=$1

NUM_EXECUTORS=${NUM_EXECUTORS:-1}
EXEC_MEMORY=${EXEC_MEMORY:-512m}
TOTAL_EXEC_CORES=${TOTAL_EXEC_CORES:-1}
DRIVER_MEMORY=${DRIVER_MEMORY:-512m}

echo "Submitting: ${PYSPARK_SCRIPT}"
echo "  --driver-memory ${DRIVER_MEMORY}"
echo "  --executor-memory ${EXEC_MEMORY}"
echo "  --total-executor-cores ${TOTAL_EXEC_CORES}"
echo "  --num-executors ${NUM_EXECUTORS}"

spark-submit                                    \
  --deploy-mode client                          \
  --driver-memory    ${DRIVER_MEMORY}           \
  --executor-memory  ${EXEC_MEMORY}             \
  --total-executor-cores ${TOTAL_EXEC_CORES}    \
  --num-executors    ${NUM_EXECUTORS}            \
  --py-files         /app/utils/spark_utils.py  \
  ${PYSPARK_SCRIPT}
