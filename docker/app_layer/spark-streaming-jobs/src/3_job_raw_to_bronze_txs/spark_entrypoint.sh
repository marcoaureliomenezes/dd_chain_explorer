#!/bin/bash

PYSPARK_FILEPATH="/app/3_job_raw_to_bronze_txs/app.py"
PYFILES_SPARK_PATH="/app/utils/spark_utils.py"
PYFILES_LOGGER_PATH="/app/utils/logger_utils.py"

TOTAL_EXEC_CORES=1
EXEC_MEMORY=512M

echo "spark-submit                                                 "
echo "    --deploy-mode client                                     "
echo "    --executor-memory ${EXEC_MEMORY}                         "
echo "    --total-executor-cores ${TOTAL_EXEC_CORES}               "
echo "    --py-files ${PYFILES_PATH}                               "
echo "    ${PYFILES_SPARK_PATH},${PYFILES_LOGGER_PATH}             "


spark-submit \
--deploy-mode client \
--executor-memory ${EXEC_MEMORY} \
--total-executor-cores ${TOTAL_EXEC_CORES} \
--py-files ${PYFILES_SPARK_PATH},${PYFILES_LOGGER_PATH} \
${PYSPARK_FILEPATH}