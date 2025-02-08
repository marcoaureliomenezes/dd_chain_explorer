#!/bin/bash


PYSPARK_SCRIPT=$1
PYFILES_SPARK_PATH="/app/utils/spark_utils.py"
PYFILES_SCHEMA_REGISTRY_PATH="/app/utils/schema_registry_utils.py"

# get an environment variable called EXEC_MEMORY with default value 1G

EXEC_MEMORY=${EXEC_MEMORY:-1G}
TOTAL_EXEC_CORES=${TOTAL_EXEC_CORES:-1}
DRIVER_MEMORY=${DRIVER_MEMORY:-1G}

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
--driver-memory $DRIVER_MEMORY \
--py-files ${PYFILES_SPARK_PATH},${PYFILES_SCHEMA_REGISTRY_PATH} \
${PYSPARK_SCRIPT}