#!/bin/bash

PYSPARK_FILEPATH=${1}
PYFILES_SPARK="/app/utils/spark_utils.py"
PYFILES_MAINTENANCE="/app/1_iceberg_maintenance/ice_stream_maintainer.py"
PYFILES_LOGGING="/app/utils/logger_utils.py"

TOTAL_EXEC_CORES=2
EXEC_MEMORY=2G

echo "spark-submit                                                                      "
echo "    --deploy-mode client                                                          "
echo "    --executor-memory ${EXEC_MEMORY}                                              "
echo "    --total-executor-cores ${TOTAL_EXEC_CORES}                                    "
echo "    ${PYFILES_SPARK}                                                              "
echo "    Script: ${PYSPARK_FILEPATH},${PYFILES_MAINTENANCE},${PYFILES_LOGGING}         "

spark-submit                                                                            \
--deploy-mode client                                                                    \
--total-executor-cores $TOTAL_EXEC_CORES                                                \
--executor-memory $EXEC_MEMORY                                                          \
--num-executors 2                                                                       \
--py-files ${PYFILES_SPARK},${PYFILES_MAINTENANCE},${PYFILES_LOGGING}                   \
${PYSPARK_FILEPATH}