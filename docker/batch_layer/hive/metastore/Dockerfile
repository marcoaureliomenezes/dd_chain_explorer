FROM marcoaureliomenezes/dm-hive-base:1.0.0


HEALTHCHECK --interval=30s --timeout=30s --retries=5 CMD [ "curl", "-f", "http://localhost:9083/" ] || exit 1