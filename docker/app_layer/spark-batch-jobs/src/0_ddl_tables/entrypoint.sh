#!/bin/bash

PYSPARK_FILEPATH=${1}
PYFILES_DDL_SCRIPTS="/app/0_ddl_tables/table_creator.py"
PYFILES_SPARK="/app/utils/spark_utils.py"
PYFILES_ICEBERG="/app/utils/iceberg_utils.py"

TOTAL_EXEC_CORES=1
EXEC_MEMORY=1G

echo "spark-submit                                                          "
echo "    --deploy-mode client                                              "
echo "    --executor-memory ${EXEC_MEMORY}                                  "
echo "    --total-executor-cores ${TOTAL_EXEC_CORES}                        "
echo "    ${PYFILES_SPARK},${PYFILES_DDL_SCRIPTS},${PYFILES_ICEBERG}        "
echo "    Script: ${PYSPARK_FILEPATH}                                       "

spark-submit \
--deploy-mode client \
--total-executor-cores $TOTAL_EXEC_CORES \
--executor-memory $EXEC_MEMORY \
--py-files ${PYFILES_SPARK},${PYFILES_DDL_SCRIPTS},${PYFILES_ICEBERG} \
${PYSPARK_FILEPATH}