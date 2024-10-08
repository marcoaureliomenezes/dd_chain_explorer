#!/bin/bash


PYSPARK_FILEPATH="/app/2_raw_to_bronze_logs_fast/app.py"
PYFILES_SPARK_PATH="/app/utils/spark_utils.py"
PYFILES_SCHEMA_REGISTRY_PATH="/app/utils/schema_registry_utils.py"



TOTAL_EXEC_CORES=1
EXEC_MEMORY=512M

echo "spark-submit                                                 "
echo "    --deploy-mode client                                     "
echo "    --executor-memory ${EXEC_MEMORY}                         "
echo "    --total-executor-cores ${TOTAL_EXEC_CORES}               "
echo "    --py-files ${PYFILES_PATH}                               "
echo "    ${PYFILES_SPARK_PATH},${PYFILES_SCHEMA_REGISTRY_PATH}    "


spark-submit \
--master ${SPARK_MASTER_URL} \
--deploy-mode client \
--total-executor-cores $TOTAL_EXECUTOR_CORES \
--executor-memory $EXECUTOR_MEMORY \
--py-files ${PYFILES_SPARK_PATH},${PYFILES_SCHEMA_REGISTRY_PATH} \
${PYSPARK_FILEPATH}