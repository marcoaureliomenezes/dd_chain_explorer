#!/bin/bash

PYSPARK_SCRIPT=$1

NUM_EXECUTORS=${NUM_EXECUTORS:-1}
EXEC_MEMORY=${EXEC_MEMORY:-512m}
TOTAL_EXEC_CORES=${TOTAL_EXEC_CORES:-1}
DRIVER_MEMORY=${DRIVER_MEMORY:-512m}

# Detect Spark version and Scala suffix at runtime so package coordinates always match
SPARK_VERSION=$(/opt/bitnami/spark/bin/spark-submit --version 2>&1 | grep -oP '(?<=version )\d+\.\d+\.\d+' | head -1)
SPARK_MAJOR=$(echo "${SPARK_VERSION}" | cut -d. -f1)
if [ "${SPARK_MAJOR}" -ge 4 ]; then
    SCALA_SUFFIX="2.13"
else
    SCALA_SUFFIX="2.12"
fi
echo "Detected Spark version: ${SPARK_VERSION} (Scala ${SCALA_SUFFIX})"

KAFKA_PKG="org.apache.spark:spark-sql-kafka-0-10_${SCALA_SUFFIX}:${SPARK_VERSION}"
AVRO_PKG="org.apache.spark:spark-avro_${SCALA_SUFFIX}:${SPARK_VERSION}"

echo "Submitting: ${PYSPARK_SCRIPT}"
echo "  --packages ${KAFKA_PKG},${AVRO_PKG}"
echo "  --driver-memory ${DRIVER_MEMORY}"
echo "  --executor-memory ${EXEC_MEMORY}"
echo "  --total-executor-cores ${TOTAL_EXEC_CORES}"
echo "  --num-executors ${NUM_EXECUTORS}"

spark-submit                                    \
  --deploy-mode client                          \
  --packages "${KAFKA_PKG},${AVRO_PKG}"         \
  --driver-memory    ${DRIVER_MEMORY}           \
  --executor-memory  ${EXEC_MEMORY}             \
  --total-executor-cores ${TOTAL_EXEC_CORES}    \
  --num-executors    ${NUM_EXECUTORS}            \
  --py-files         /app/utils/spark_utils.py  \
  ${PYSPARK_SCRIPT}
