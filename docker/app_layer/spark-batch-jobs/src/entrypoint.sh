#!/bin/bash

PYSPARK_FILEPATH=${1}
PYFILES_SPARK="/app/utils/spark_utils.py"
PYFILES_MAINTENANCE="/app/maintenance_streaming_tables/iceberg_maintenance.py"


DRIVER_MEMORY=${DRIVER_MEMORY:-1G}
EXEC_MEMORY=${EXEC_MEMORY:-1G}
TOTAL_EXEC_CORES=${TOTAL_EXEC_CORES:-1}
NUM_EXECUTORS=${NUM_EXECUTORS:-1}


echo "spark-submit                                                                      "
echo "    --deploy-mode client                                                          "
echo "    --driver-memory ${DRIVER_MEMORY}                                              "
echo "    --executor-memory ${EXEC_MEMORY}                                              "
echo "    --total-executor-cores ${TOTAL_EXEC_CORES}                                    "
echo "    --num-executors ${NUM_EXECUTORS}                                              "
echo "    ${PYFILES_SPARK}.${PYFILES_MAINTENANCE}                                       "
echo "    Script: ${PYSPARK_FILEPATH},                                                  "


spark-submit                                                                            \
--deploy-mode client                                                                    \
--driver-memory ${DRIVER_MEMORY}                                                        \
--executor-memory ${EXEC_MEMORY}                                                        \
--total-executor-cores ${TOTAL_EXEC_CORES}                                              \
--num-executors ${NUM_EXECUTORS}                                                        \
--py-files ${PYFILES_SPARK},${PYFILES_MAINTENANCE}                                      \
${PYSPARK_FILEPATH}