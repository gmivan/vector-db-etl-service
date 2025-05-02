import asyncio
import glob
import requests
import aiohttp
import numpy as np
import pandas as pd
import time
import os
from apscheduler.schedulers.background import BackgroundScheduler
from tqdm import tqdm
import traceback
from fastapi import FastAPI, Request
import uvicorn
from typing import List, Tuple, Any
from huggingface_hub import snapshot_download
import datetime
import signal
import sys
from qdrant_client import AsyncQdrantClient, models
from pydantic import BaseModel
from worker.schemas import UpsertQdrantEmbeddingsRequest

pd.options.mode.copy_on_write = True

# Constants
DATASET_NAME = 'anonymous/multimodal-dataset'
UPDATE_INTERVAL_MINUTES = 10
ESSENTIAL_COLUMNS = ['youtube_id', 'start_time', 'end_time', "video_embed"]
ELEMENTS_START = 0
ELEMENTS_END = 1000000000
ELEMENTS_MAX = ELEMENTS_END - ELEMENTS_START

class DataModel(BaseModel):
    ids: List[str]
    embeddings: List[List[float]]
    payload: List[dict[str, Any]]

class DatasetProcessor:
    HF_RETRY_INTERVAL = 20  # seconds

    def __init__(self):
        print(f"Initializing Dataset Processor")
        self.should_exit = False
        self.url = "https://huggingface.co/api/datasets/anonymous/multimodal-dataset/parquet/default/train"
        self.worker_url = os.environ.get('WORKER_URL', 'http://localhost:8646')
        
        self.working_dir = os.path.abspath("/mnt/hf/24/dataset")
        self.dataset_dir = os.path.join(self.working_dir, "hf_dataset/default/train")
        self.processed_dir = os.path.join(self.working_dir, "processed")
        self.completed_dir = os.path.join(self.working_dir, "completed")
        
        # Create necessary directories
        for dir_path in [self.working_dir, self.dataset_dir, self.processed_dir, self.completed_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Initialize Qdrant client
        self.qdrant_client = AsyncQdrantClient(
            host=os.environ.get('QDRANT_HOST', 'localhost'),
            port=int(os.environ.get('QDRANT_PORT', '6333')),
            api_key=os.environ.get('QDRANT_API_KEY')
        )
        
        self.collection_name = f'embeddings-{os.environ.get("EMBEDDING_MODEL", "text-embedding-ada-002")}'
        self.n_elements = 0

    def _get_parquet_file_path(self, file_id):
        return os.path.join(self.dataset_dir, f"{file_id}.parquet")

    @staticmethod
    def _extract_file_id(url):
        return url.split('/')[-1].split('.')[0]

    async def _is_db_uptodate(self):
        try:
            # Check Qdrant collection
            if not await self.qdrant_client.collection_exists(self.collection_name):
                return False
            
            # Get count from worker service
            response = requests.get(f"{self.worker_url}/get_qdrant_count/{self.collection_name}")
            if response.status_code == 200:
                self.n_elements = int(response.text)
                print(f"Number of elements in Qdrant: {self.n_elements}")
                
                if self.n_elements >= ELEMENTS_MAX:
                    print("Reached maximum number of elements. Exiting...")
                    self.should_exit = True
                    return True
                
                # Check for unprocessed files
                dataset_files = self.get_dataset_files()
                processed_files = self.get_processed_files()
                new_parquet_files_count = len(dataset_files) - len(processed_files)
                
                if new_parquet_files_count:
                    print(f"Found {new_parquet_files_count} unprocessed local files. DB is not up-to-date.")
                    return False
                
                return True
            else:
                print(f"Failed to fetch count: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"Error checking database status: {e}")
            return False

    def _load_parquet_chunk(self, filename=None, file_id=None):
        if filename is None and file_id is None:
            raise ValueError("Either filename or file_id must be provided")
        
        if filename is None:
            filename = self._get_parquet_file_path(file_id)
        
        print(f"Loading parquet file: {filename}")
        df = pd.read_parquet(filename)
        
        # Ensure essential columns exist
        missing_columns = [col for col in ESSENTIAL_COLUMNS if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing essential columns: {missing_columns}")
        
        # Process embeddings
        def quantize_video_embed(embed):
            if isinstance(embed, list):
                return np.array(embed, dtype=np.float32)
            return embed
        
        df['video_embed'] = df['video_embed'].apply(quantize_video_embed)
        return df

    def get_dataset_files(self):
        return glob.glob(os.path.join(self.dataset_dir, "*.parquet"))

    def get_processed_files(self):
        return glob.glob(os.path.join(self.processed_dir, "*.parquet"))

    @staticmethod
    def convert_to_relative_path(startpath, files):
        return [os.path.relpath(f, startpath) for f in files]

    @staticmethod
    def ensure_directory_exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    def mark_as_completed(self, filename):
        completed_path = os.path.join(self.completed_dir, os.path.basename(filename))
        self.ensure_directory_exists(completed_path)
        os.rename(filename, completed_path)

    async def _update_db(self, new_chunk):
        try:
            # Prepare data for Qdrant
            points = []
            for _, row in new_chunk.iterrows():
                point = {
                    'id': str(row['youtube_id']),
                    'vector': row['video_embed'].tolist(),
                    'payload': {
                        'youtube_id': row['youtube_id'],
                        'start_time': row['start_time'],
                        'end_time': row['end_time'],
                    }
                }
                points.append(point)
            
            # Create collection if it doesn't exist
            if not await self.qdrant_client.collection_exists(self.collection_name):
                await self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=len(new_chunk['video_embed'].iloc[0]),
                        distance=models.Distance.COSINE,
                    ),
                )
            
            # Upsert points in batches
            batch_size = 1000
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                await self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                )
                print(f"Upserted batch of {len(batch)} points")
            
            return True
        except Exception as e:
            print(f"Error updating database: {e}")
            return False

    def _parquet_to_db(self, parquet_files):
        for file in tqdm(parquet_files):
            try:
                df = self._load_parquet_chunk(filename=file)
                asyncio.run(self._update_db(df))
                self.mark_as_completed(file)
            except Exception as e:
                print(f"Error processing file {file}: {e}")

    def _load_initial_data(self):
        if not os.path.exists(self.dataset_dir):
            print("Downloading dataset...")
            snapshot_download(
                repo_id=DATASET_NAME,
                repo_type="dataset",
                local_dir=self.working_dir,
                max_workers=4
            )
        
        parquet_files = self.get_dataset_files()
        if not parquet_files:
            raise ValueError("No parquet files found in dataset directory")
        
        self._parquet_to_db(parquet_files)

    def _update_from_hf(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            data = response.json()
            
            current_files = set(self.convert_to_relative_path(self.working_dir, self.get_dataset_files()))
            processed_files = set(self.convert_to_relative_path(self.working_dir, self.get_processed_files()))
            
            new_files = []
            for file_info in data:
                file_id = self._extract_file_id(file_info['url'])
                if file_id not in current_files and file_id not in processed_files:
                    new_files.append(file_id)
            
            if new_files:
                print(f"Found {len(new_files)} new files to process")
                self._parquet_to_db([self._get_parquet_file_path(f) for f in new_files])
            else:
                print("No new files to process")
        except Exception as e:
            print(f"Error updating from Hugging Face: {e}")

    async def run(self):
        print("Starting dataset processor")
        
        # Load initial data if needed
        if not await self._is_db_uptodate():
            print("Database not up to date, loading initial data")
            self._load_initial_data()
        
        # Set up scheduler for periodic updates
        scheduler = BackgroundScheduler()
        scheduler.add_job(self._update_from_hf, 'interval', minutes=UPDATE_INTERVAL_MINUTES)
        scheduler.start()
        
        try:
            while not self.should_exit:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            scheduler.shutdown()

def signal_handler(sig, frame):
    print("Received shutdown signal")
    processor.should_exit = True

if __name__ == "__main__":
    processor = DatasetProcessor()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    asyncio.run(processor.run())
