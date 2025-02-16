import boto3
import os
import argparse
import logging


class DataLakeExpurgator:

  
  def __init__(self, logger, bucket: str):
    self.bucket = bucket
    self.logger = logger
    self.s3_client = boto3.client('s3', endpoint_url=os.getenv("S3_URL"))
    self.s3 = boto3.resource('s3', endpoint_url=os.getenv("S3_URL"))


  def delete_objects(self, prefix: str):
    
    response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
    while response.get("Contents"):
      objects_to_delete =[{ "Key": obj["Key"] } for obj in response["Contents"]]
      for obj in objects_to_delete:
        self.logger.info(f"Deleting object {obj['Key']} from {self.bucket}")
        self.s3_client.delete_object(Bucket=self.bucket, Key=obj["Key"])
      if response.get("NextContinuationToken"):
        response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=prefix, ContinuationToken=response["NextContinuationToken"])
      else: break



if __name__ == "__main__":

  parser = argparse.ArgumentParser(description='Delete keys from S3')
  parser.add_argument('--bucket', type=str, help='S3 bucket name')
  parser.add_argument('--prefix', type=str, help='S3 key prefix', default='')
  args = parser.parse_args()
  bucket = args.bucket
  prefix = args.prefix

  LOGGER = logging.getLogger()
  LOGGER.setLevel(logging.INFO)
  LOGGER.addHandler(logging.StreamHandler())

  s3_client = boto3.client('s3',
    endpoint_url=os.getenv("S3_URL"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
  )

  expurgator = DataLakeExpurgator(LOGGER, bucket)
  expurgator.delete_objects(prefix)
