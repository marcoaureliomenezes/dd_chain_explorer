#!/bin/bash


PYSPARK_FILEPATH="/app/4_job_silver_transactions/app.py"
PYFILES_SPARK_PATH="/app/utils/spark_utils.py"
PYFILES_SCHEMA_REGISTRY_PATH="/app/utils/schema_registry_utils.py"



TOTAL_EXEC_CORES=1
EXEC_MEMORY=1G

echo "spark-submit                                                 "
echo "    --deploy-mode client                                     "
echo "    --executor-memory ${EXEC_MEMORY}                         "
echo "    --total-executor-cores ${TOTAL_EXEC_CORES}               "
echo "    --py-files ${PYFILES_PATH}                               "
echo "    ${PYFILES_SPARK_PATH},${PYFILES_SCHEMA_REGISTRY_PATH}    "
echo "    ${PYSPARK_FILEPATH}                                      "

spark-submit \
--deploy-mode client \
--total-executor-cores $TOTAL_EXEC_CORES \
--executor-memory $EXEC_MEMORY \
--driver-memory 1G \
--py-files ${PYFILES_SPARK_PATH},${PYFILES_SCHEMA_REGISTRY_PATH} \
${PYSPARK_FILEPATH}