from abc import ABC, abstractmethod
from typing import Generator, Dict, Any, Self, Callable

class ChainExtractor(ABC):

  def __init__(self):
    pass

  @abstractmethod
  def src_config(self, src_properties: Dict[str, Any]) -> Self:
    pass

  @abstractmethod
  def sink_config(self, sink_properties: Dict[str, Any]) -> Self:
    pass

  @abstractmethod
  def run(self, callback: Callable) -> None:
    pass


  def consuming_topic(self, consumer) -> Generator:
    while True:
      msg = consumer.poll(timeout=0.1)
      if msg: yield {"key": msg.key(), "value": msg.value()}


