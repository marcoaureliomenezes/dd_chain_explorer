CREATE KEYSPACE IF NOT EXISTS operations WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

DROP TABLE IF EXISTS api_keys_node_providers;

CREATE TABLE IF NOT EXISTS api_keys_node_providers (
  name TEXT PRIMARY KEY, 
  start TEXT, 
  end TEXT, 
  num_req_1d INT,
  last_req TEXT);