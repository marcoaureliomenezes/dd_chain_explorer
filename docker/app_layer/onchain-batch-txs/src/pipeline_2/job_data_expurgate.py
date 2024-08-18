import logging
import glob
import os



class DataExpurgator:

  def __init__(self, logger):
    self.logger = logger


  def expurgate_data(self, path):
    for file in glob.glob(path + "*"):
      #os.remove(file)
      self.logger.info(f"File {file} removed.")
    #os.rmdir(path)


def main(contract, **kwargs):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    print("AQUUUUUUUUUI")
    print(kwargs["execution_date"])
    print(kwargs)

    start_timestamp = 1722291913
    end_timestamp = 1722297513

    logger.info(f"Contract: {contract}")
    logger.info(f"Start Timestamp: {start_timestamp}")
    logger.info(f"End Timestamp: {end_timestamp}")

    path = f"./tmp/{start_timestamp}_{end_timestamp}/{contract}/"
    expurgator = DataExpurgator(logger)
    expurgator.expurgate_data(path)

if __name__ == '__main__':
    
  START_TIME = 1722291913
  END_TIME = 1722297513
  ADDRESS = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
  main(ADDRESS)


