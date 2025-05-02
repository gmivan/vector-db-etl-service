import os
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import AsyncQdrantClient

from worker.config import MongoDBConfig, QdrantConfig

def add_cors_middleware(app: FastAPI) -> None:
    origins = ['*']
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

async def get_mongodb_async_database() -> AsyncIOMotorClient:
    config = MongoDBConfig()
    connection_string = f"mongodb://{config.host}:{config.port}"
    if config.username and config.password:
        connection_string = f"mongodb://{config.username}:{config.password}@{config.host}:{config.port}"
    
    client = AsyncIOMotorClient(connection_string)
    return client[config.database]

async def get_qdrant_async_client() -> AsyncQdrantClient:
    config = QdrantConfig()
    return AsyncQdrantClient(
        host=config.host,
        port=config.port,
        api_key=config.api_key
    )

def get_package_version() -> str:
    back_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')
    pyproject_path = os.path.abspath(os.path.join(back_root, 'pyproject.toml'))
    with open(pyproject_path, 'rb') as f:
        import tomllib
        pyproject = tomllib.load(f)
        return str(pyproject['tool']['poetry']['version'])
