FROM local/spark:3.5

WORKDIR /app
USER root

RUN install_packages curl wget

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY ./src /app
RUN chmod +x /app/entrypoint.sh

COPY conf/spark-defaults.conf /opt/bitnami/spark/conf/spark-defaults.conf

ENTRYPOINT ["sleep", "infinity"]
