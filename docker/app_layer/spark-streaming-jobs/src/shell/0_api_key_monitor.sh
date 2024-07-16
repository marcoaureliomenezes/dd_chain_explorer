#!/bin/bash


# GET ENVIRONMENT VARIABLES

# SPARK_MASTER_URL


SPARK_APPLICATION_PYTHON_LOCATION=$1

TOTAL_EXECUTOR_CORES=${NUM_EXECUTOR_CORES:-1}
EXECUTOR_MEMORY=${EXECUTOR_MEMORY:-512M}

echo "spark-submit                                              "
echo " --master ${SPARK_MASTER_URL}                             "
echo " --total-executor-cores $TOTAL_EXECUTOR_CORES             "
echo " --executor-memory $EXECUTOR_MEMORY                       "
echo " --packages ${KAFKA_CONNECTOR},${SCYLLA_CONNECTOR}        "
echo " ${SPARK_APPLICATION_PYTHON_LOCATION}                     "


spark-submit \
--master ${SPARK_MASTER_URL} \
--deploy-mode client \
--total-executor-cores $TOTAL_EXECUTOR_CORES \
--executor-memory $EXECUTOR_MEMORY \
--packages ${KAFKA_CONNECTOR},${SCYLLA_CONNECTOR} \
${SPARK_APPLICATION_PYTHON_LOCATION}