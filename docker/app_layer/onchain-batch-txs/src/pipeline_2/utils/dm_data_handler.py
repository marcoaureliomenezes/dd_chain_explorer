import json
import hashlib
from cryptography.fernet import Fernet
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import logging


class DMDataHandler:
    

  def __init__(self, logger):
      self.logger = logger
        

  def encrypt_data(self, data):
    key = Fernet.generate_key()
    self.logger.info(f"Generated encryption key: {key.decode()}")
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    self.logger.info(f"Data encrypted: {encrypted}")
    return encrypted, key


  def decrypt_data(self, data, key):
    fernet = Fernet(key)
    decrypted = fernet.decrypt(data)
    return decrypted.decode()

  def generate_hash(self, data):
    hash_object = hashlib.sha256(data.encode())
    return hash_object.hexdigest()
  
  def write_compressed_parquet(self, data, path):
    df = pd.DataFrame({"encrypted_data": [data.decode()]})
    table = pa.Table.from_pandas(df)
    pq.write_table(table, path, compression='SNAPPY')


if __name__ == "__main__":
   
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.INFO)


  dm_encrypt = DmEncrypt(logger)
  
  data_test = {
      "name": "John Doe",
      "age": 30,
      "city": "New York"
  }

  str_data = json.dumps(data_test)
  data_encrypted, key = dm_encrypt.encrypt_data(str_data)
  
  # Gerar hash dos dados originais
  data_hash = dm_encrypt.generate_hash(str_data)

  print(f"Data hash: {data_hash}")

  print(f"Data encrypted: {data_encrypted}, Key: {key}")

  data_dict = {"encrypted_data": [data_encrypted.decode()]}
  df = pd.DataFrame(data_dict)

  # Escrever os dados encriptados no formato Parquet
  table = pa.Table.from_pandas(df)
  print(table)
  #pq.write_table(table, 'encrypted_data.parquet', compression='SNAPPY')
  
  # Decodificar dados

  data_decoded = dm_encrypt.decrypt_data(data_encrypted, key)
  print(f"Data decoded: {data_decoded}")
  

