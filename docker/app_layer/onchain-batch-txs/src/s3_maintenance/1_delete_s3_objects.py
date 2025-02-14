import boto3
import os
import argparse
import logging


class DataLakeExpurgator:

  
  def __init__(self, logger, bucket: str):
    self.bucket = bucket
    self.logger = logger
    self.s3_client = boto3.client('s3',
      endpoint_url=os.getenv("S3_URL"),
      aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
      aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )


  def delete_objects(self, prefix: str):
    response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
    print(response)
    if not response.get("Contents"):
      self.logger.info(f"No objects found with prefix {prefix}")
      return
    keys = [obj["Key"] for obj in response["Contents"]]
    self.logger.info(f"Deleting objects from {self.bucket} with prefix {prefix}")
    for key in keys:
      self.s3_client.delete_object(Bucket=self.bucket, Key=key)
      self.logger.info(f"Object {key} deleted")


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
