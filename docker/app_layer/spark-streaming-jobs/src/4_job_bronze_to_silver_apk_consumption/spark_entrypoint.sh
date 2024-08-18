#!/bin/bash


SPARK_APPLICATION_PYTHON_LOCATION="/app/python/1_mined_blocks_raw.py"

echo "spark-submit                                              "
echo " --master ${SPARK_MASTER_URL}                             "
echo " --total-executor-cores 1                                 "
echo " ${SPARK_APPLICATION_PYTHON_LOCATION}                     "


spark-submit \
--master ${SPARK_MASTER_URL} \
--deploy-mode client \
--executor-memory 512M \
--total-executor-cores 1 \
${SPARK_APPLICATION_PYTHON_LOCATION}
