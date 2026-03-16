import logging


class KafkaLoggingHandler(logging.Handler):
    """logging.Handler that forwards log records to a Kafka AVRO topic.

    The producer must be an AVRO Serializing Producer configured with
    the ``0_application_logs_avro.json`` schema (fields: timestamp, logger,
    level, filename, function_name, message).

    Usage::

        schema_app_logs = get_schema(
            schema_name="application-logs-schema",
            schema_path="schemas/0_application_logs_avro.json",
        )
        producer_logs = handler_kafka.create_avro_producer(PRODUCER_CONF, schema_app_logs)
        logger.addHandler(KafkaLoggingHandler(producer_logs, TOPIC_LOGS))
    """

    def __init__(self, producer, topic: str):
        super().__init__()
        self.producer = producer
        self.topic = topic

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = {
                "timestamp": int(record.created),
                "logger": record.name,
                "level": record.levelname,
                "filename": record.filename,
                "function_name": record.funcName,
                "message": record.getMessage(),
            }
            self.producer.produce(self.topic, key=record.filename, value=msg)
            self.producer.flush()
        except Exception:
            self.handleError(record)


class ConsoleLoggingHandler(logging.Handler):
    """Simple logging.Handler that prints formatted records to stdout."""

    def __init__(self):
        super().__init__()
        self.formatter = logging.Formatter('%(asctime)s;%(name)s;%(levelname)s;%(message)s')

    def emit(self, record: logging.LogRecord) -> None:
        print(self.format(record))
