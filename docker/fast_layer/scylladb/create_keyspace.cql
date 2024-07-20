CREATE KEYSPACE IF NOT EXISTS operations WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS operations.api_keys_node_providers (
  name text PRIMARY KEY,
  start text,
  end text,
  num_req_1d int,
  last_req text

);