from abc import ABC, abstractmethod
from typing import Dict, Self
from pyspark.sql.streaming import StreamingQuery
#Creating an interface for DMStreaming

class IDmStreaming(ABC):

    @abstractmethod
    def config_source(self, src_properties: Dict[str, str]) -> Self:
        pass

    @abstractmethod
    def config_sink(self, sink_properties: Dict[str, str]) -> Self:
        pass

    @abstractmethod
    def extract(self) -> Self:
        pass

    @abstractmethod
    def transform(self, *args) -> Self:
        pass

    @abstractmethod
    def load(self) -> StreamingQuery:
        pass

    @abstractmethod
    def load_to_console(self) -> StreamingQuery:
        pass


