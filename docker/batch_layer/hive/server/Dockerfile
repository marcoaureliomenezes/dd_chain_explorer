FROM marcoaureliomenezes/dm-hive-base:1.0.0


HEALTHCHECK --interval=30s --timeout=30s --retries=5 CMD [ "curl", "-f", "http://localhost:10000/" ] || exit 1