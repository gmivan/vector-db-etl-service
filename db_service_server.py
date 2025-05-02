"""
How to run with gunicorn as load balancer with graceful restart:

pip install gunicorn uvicorn-worker
pm2 start db_service_server.config.js && pm2 logs

To restart gracefully:
pm2 sendSignal SIGHUP db_service_server && pm2 logs
"""

import asyncio
import traceback
from fastapi import FastAPI, Request
import uvicorn
from typing import List, Tuple
import time
import aiohttp

import vector_db_connect_wrapper

TIMEOUT = 5
NOVELTY_SENTINEL = -1
SIMILARITY_SENTINEL = 2

while True:
    try:
        db = vector_db_connect_wrapper.DB(index='omega')
        break
    except aiohttp.ClientConnectionError:
        print("Error connecting to the database. Retrying in 30 seconds...")
        time.sleep(30)

app = FastAPI()

@app.post("/get_novelty_scores")
async def get_novelty_scores(
        embeddings: List[List[float]]
) -> List[float]:
    start_time = time.time()
    results = await db.get_similarity_scores(embeddings)
    novelty_scores = [1 - result if result is not None and result != SIMILARITY_SENTINEL 
                      else NOVELTY_SENTINEL 
                      for result in results]
    print(f"Returning {len(novelty_scores)} novelty scores in {time.time() - start_time:.2f} s: {novelty_scores}")
    return novelty_scores


if __name__ == "__main__":

    try:
        uvicorn.run(app, host="0.0.0.0", port=8770, timeout_graceful_shutdown=30)
    except KeyboardInterrupt:
        print("Server stopped.")
