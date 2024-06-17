#!/bin/bash


SPARK_APPLICATION_PYTHON_LOCATION="/app/python/1_handle_simple_txs.py"

echo "spark-submit                                              "
echo " --master ${SPARK_MASTER_URL}                             "
echo " --total-executor-cores 1                                 "
echo " --packages ${KAFKA_CONNECTOR},${SCYLLA_CONNECTOR}        "
echo " ${SPARK_APPLICATION_PYTHON_LOCATION}                     "


spark-submit \
--master ${SPARK_MASTER_URL} \
--deploy-mode client \
--executor-memory 512M \
--total-executor-cores 1 \
--packages ${KAFKA_CONNECTOR},${SCYLLA_CONNECTOR} \
${SPARK_APPLICATION_PYTHON_LOCATION}
