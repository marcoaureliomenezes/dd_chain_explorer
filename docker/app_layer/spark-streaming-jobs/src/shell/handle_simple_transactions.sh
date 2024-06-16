#!/bin/bash


SPARK_APPLICATION_PYTHON_LOCATION="/app/python/api_key_monitor_2.py"

echo "spark-submit                                              "
echo " --master ${SPARK_MASTER_URL}                             "
echo " --total-executor-cores 1                                 "
echo " --packages ${KAFKA_CONNECTOR},${SCYLLA_CONNECTOR}        "
echo " ${SPARK_APPLICATION_PYTHON_LOCATION}                     "


spark-submit \
--master ${SPARK_MASTER_URL} \
--deploy-mode client \
--total-executor-cores 1 \
--packages ${KAFKA_CONNECTOR},${SCYLLA_CONNECTOR} \
${SPARK_APPLICATION_PYTHON_LOCATION}
