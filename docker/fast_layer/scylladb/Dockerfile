FROM scylladb/scylla:5.4



COPY ./create_keyspace.cql /docker-entrypoint-initdb.d/create_keyspace.cql



COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]



