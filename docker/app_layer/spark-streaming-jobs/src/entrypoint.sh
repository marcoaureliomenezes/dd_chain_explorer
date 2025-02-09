#!/bin/bash


PYSPARK_SCRIPT=$1
PYFILES_SPARK_PATH="/app/utils/spark_utils.py"
PYFILES_SC_PATH="/app/utils/schema_registry_utils.py"
PYFILES_LOGGING_PATH="/app/utils/logging_utils.py"

# get an environment variable called EXEC_MEMORY with default value 1G

NUM_EXECUTORS=${NUM_EXECUTORS:-1}
EXEC_MEMORY=${EXEC_MEMORY:-1G}
TOTAL_EXEC_CORES=${TOTAL_EXEC_CORES:-1}
DRIVER_MEMORY=${DRIVER_MEMORY:-1G}

echo "spark-submit                                                              "
echo "    --deploy-mode client                                                  "
echo "    --driver-memory ${DRIVER_MEMORY}                                      "
echo "    --executor-memory ${EXEC_MEMORY}                                      "
echo "    --total-executor-cores ${TOTAL_EXEC_CORES}                            "
echo "    --py-files ${PYFILES_PATH}                                            "
echo "    ${PYFILES_SPARK_PATH},${PYFILES_SC_PATH},${PYFILES_LOGGING_PATH}      "
echo "    ${PYSPARK_FILEPATH}                                                   "

echo "Running spark-submit"

spark-submit                                                                    \
--deploy-mode client                                                            \
--driver-memory $DRIVER_MEMORY                                                  \
--total-executor-cores $TOTAL_EXEC_CORES                                        \
--executor-memory $EXEC_MEMORY                                                  \
--num-executors ${NUM_EXECUTORS}                                                \
--py-files ${PYFILES_SPARK_PATH},${PYFILES_SC_PATH},${PYFILES_LOGGING_PATH}     \
${PYSPARK_SCRIPT}