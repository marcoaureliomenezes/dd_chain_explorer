CREATE KEYSPACE IF NOT EXISTS operations WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};


CREATE TABLE IF NOT EXISTS api_keys_node_providers (
  start TEXT, 
  end TEXT, 
  name TEXT PRIMARY KEY, 
  num_req_1D INT);