from dataclasses import dataclass
import logging
import os
import sys
from typing import Any, Literal, Optional

from pydantic import BaseModel


class QdrantConfig(BaseModel):
    url: str = os.environ.get('QDRANT_URL', 'http://localhost:6333/')
    prefer_grpc: bool = True
    timeout: int = 5
    api_key: str | None = os.environ.get('QDRANT__SERVICE__API_KEY')

    def model_post_init(self, __context: Any) -> None:
        # update with environment variables in real time
        self.url = os.environ.get('QDRANT_URL', 'http://localhost:6333/')
        self.api_key = os.environ.get('QDRANT__SERVICE__API_KEY')


# @dataclass
# class LoggingConfig:  # pydantic doesn't work with sys.stdout
#     level: str = os.environ.get('LOGGING_LEVEL', 'INFO')
#     stream: ... = sys.stdout
#     format: str = '{asctime:^20s} | {levelname:^8s} | {name:^10s} | {funcName:^10s} | {message:s}'
#     style: Literal['%', '{', '$'] = '{'

#     def __post_init__(self) -> None:
#         if self.level not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
#             logging.warning(f'Invalid LOGGING_LEVEL: {self.level}, using INFO instead')
#             self.level = 'INFO'


@dataclass
class LoggingConfig:
    level: str = os.environ.get('LOGGING_LEVEL', 'INFO')
    stream: ... = sys.stdout
    format: str = '{asctime:^20s} | {levelname:^8s} | {name:^10s} | {funcName:^10s} | {message:s}'
    style: Literal['%', '{', '$'] = '{'
    filename: str = 'worker_3.log'  # Specify the log file
    filemode: str = 'a'  # Append mode for the log file
    
    def __post_init__(self) -> None:
        if self.level not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
            logging.warning(f'Invalid LOGGING_LEVEL: {self.level}, using INFO instead')
            self.level = 'INFO'
        
        logging.basicConfig(
            level=self.level,
            format=self.format,
            style=self.style,
            handlers=[
                logging.StreamHandler(self.stream),  # For stdout
                logging.FileHandler(self.filename, mode=self.filemode)  # For file logging
            ]
        )


class MongoDBConfig:
    def __init__(self):
        self.host = os.environ.get('MONGODB_HOST', 'localhost')
        self.port = int(os.environ.get('MONGODB_PORT', '27017'))
        self.database = os.environ.get('MONGODB_DATABASE', 'worker')
        self.username = os.environ.get('MONGODB_USERNAME')
        self.password = os.environ.get('MONGODB_PASSWORD')


class OpenAIConfig:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.default_model = os.environ.get('OPENAI_DEFAULT_MODEL', 'text-embedding-ada-002')


class Config:
    def __init__(self):
        self.logging = LoggingConfig()
        self.mongodb = MongoDBConfig()
        self.qdrant = QdrantConfig()
        self.openai = OpenAIConfig()
        self.worker_port = int(os.environ.get('WORKER_PORT', '8771'))
        self.worker_host = os.environ.get('WORKER_HOST', '0.0.0.0')

