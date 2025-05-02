import time
import traceback

import requests
from requests.auth import HTTPBasicAuth
import json

import datetime
import backoff
import aiohttp
import asyncio
import torch
import torch.nn.functional as F
import dotenv
import random

import os
from urllib3.exceptions import InsecureRequestWarning
import urllib3
import subprocess

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(InsecureRequestWarning)

# Telegram bot token and chat ID
TELEGRAM_BOT_TOKEN = '6667471259:AAFm-6ijwoODIFf6kUPCov0s02gpzmyB5yg'
TELEGRAM_CHAT_ID = '-1002088120831'


def restart_pm2():
    script_path = os.path.join(os.getcwd(), "restart_opensearch.sh")
    try:
        print(f"Script {script_path} will be executed now.")
        subprocess.Popen(f"bash {script_path} & disown", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Restart script executed successfully")
    except Exception as e:
        print(f"Failed to execute restart script: {e}")

def get_public_ip_from_web():
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        response.raise_for_status()
        ip_info = response.json()
        public_ip = ip_info.get('ip')
    except requests.RequestException as e:
        print(f"Error retrieving public IP: {e}")
        public_ip = None
    return public_ip

def get_public_ip():
    # SSH_CONNECTION=185.111.11.115 4251 182.8.1.212 22
    ssh_connection = os.getenv('SSH_CONNECTION')
    if ssh_connection:
        parts = ssh_connection.split()
        if len(parts) >= 4:
            # Return the second IP address (third element in the list)
            return parts[2]
        else:
            print("SSH_CONNECTION does not contain the expected number of parts.")
    else:
        print("SSH_CONNECTION environment variable is not set.")

        return get_public_ip_from_web()

    return None


class DB:

    UPTIME_CHECK_INTERVAL = 60  # seconds

    def __init__(self, index, create=False):
        '''
        Database interface class with helper functions
        :param index: name of the index
        :param create: if True, create the index if it does not exist
        '''
        dotenv.load_dotenv()
        self.username = "admin"
        self.password = os.getenv('OPENSEARCH_PASSWORD')
        self.index_name = index
        self.url = f'https://127.0.0.1:14920'  # "https://5.199.172.158:14920" "https://188.214.130.112:14920"
        self.url_index = f'{self.url}/{self.index_name}'
        self.is_down = False
        self.last_uptime_check_time = 0.0
        if not self.exists():
            if create:
                self._create()
            else:
                raise Exception(f"Index {self.index_name} does not exist")
        else:
            # curl -X GET "http://localhost:9200/your_index_name/_count"
            count = self.count_items()
            print(f"Number of items in DB: {count}")
        self.name = get_public_ip()
        print(f"Server's name: {self.name}")

    def count_items(self):
        try:
            response = requests.get(self.url_index + "/_count",
                                    auth=HTTPBasicAuth(self.username, self.password), verify=False)
            data = response.json()
            return data['count']
        except Exception as e:
            print(f"Exception during getting number of items in DB: {e}")
            return 0

    def _create(self):
        headers = {'Content-Type': 'application/json'}
        data = {
            "settings": {
                "index": {
                    "number_of_shards": 128,
                    "number_of_replicas": 0,
                    "knn": True,
                    "knn.algo_param.ef_search": 100,
                    "refresh_interval": "-1"
                }
            },
            "mappings": {
                "properties": {
                    "youtube_id": {
                        "type": "keyword"
                    },
                    "start_time": {
                        "type": "integer"
                    },
                    "end_time": {
                        "type": "integer"
                    },
                    "video_embed": {
                        "type": "knn_vector",
                        "dimension": 1024,
                        "method": {
                            "name": "hnsw",
                            "space_type": "l2",
                            "engine": "faiss",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    }
                }
            }
        }

        response = requests.put(self.url_index,
                                auth=HTTPBasicAuth(self.username, self.password), verify=False,
                                headers=headers, data=json.dumps(data))
        print(response.status_code)
        print(response.json())

    def post_init(self):

        # curl -XPUT localhost:9200/omega_1/_settings -H 'content-type: application/json' -d '{"refresh_interval":"1s", "number_of_replicas":1}'
        headers = {'Content-Type': 'application/json'}
        data = {
                "index": {
                    "refresh_interval": "1s"
                }
        }

        try:
            response = requests.put(self.url_index+"/_settings",
                                    auth=HTTPBasicAuth(self.username, self.password), verify=False,
                                    headers=headers, data=json.dumps(data))
            print(response.status_code)
            print(response.json())
        except Exception as e:
            print(f"Failed to post_init: {e}")
            print(traceback.format_exc())

    def exists(self):
        try:
            response = requests.head(self.url_index,
                                    auth=HTTPBasicAuth(self.username, self.password), verify=False,
                                    )

            if response.status_code == 200:
                # print(f"Index '{self.index_name}' already exists.")
                return True
            elif response.status_code == 404:
                print(f"Index '{self.index_name}' does not exist.")
                return False
            else:
                print(f"Error: {response.status_code}")
                return False
        except aiohttp.ClientConnectionError as e:
            self.is_down = True
            print(f"Error connecting to DB: {e}")
            raise e
        except Exception as e:
            print(f"Exception while checking if DB exists: {e}")
        return False

    @backoff.on_exception(
        backoff.constant,
        (Exception,),
        interval=10,
        max_tries=5,
    )
    async def index_batch(self, batch):
        async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.username, self.password),
                                         connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                    url=f"{self.url}/_bulk",
                    data="\n".join([json.dumps(item) for item in batch]) + "\n",
                    headers={"Content-Type": "application/x-ndjson"},
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"Error indexing: {text}")
                    raise Exception(text)
                #print(f"Successfully indexed: {len(batch) // 2}")

    @backoff.on_exception(
        backoff.constant,
        (Exception,),
        interval=10,
        max_tries=20,
    )
    def index_batch_na(self, batch):
        headers = {"Content-Type": "application/x-ndjson"}

        data = "\n".join([json.dumps(item) for item in batch]) + "\n"
        start_time = time.time()
        response = requests.post(f"{self.url}/_bulk",
                                 auth=HTTPBasicAuth(self.username, self.password), verify=False,
                                 data=data, headers=headers)

        if response.status_code != 200:
            data_size_bytes = len(data.encode('utf-8'))
            print(f"Indexing {len(batch)} items. Size of data in bytes:", data_size_bytes)
            print(f"Error indexing: {response.reason} | {response.__dict__}")
            raise Exception(response.text)
        print(f"Successfully indexed {len(batch) // 2} items in {time.time()-start_time:.2f} s")

    async def bulk_knn_search(self, session, url, index, embeddings):

        res = [None] * len(embeddings)
        # Prepare the bulk search body
        bulk_body = []
        for embedding in embeddings:
            bulk_body.extend([
                json.dumps({"index": index}),
                json.dumps({
                    "query": {
                        "knn": {
                            "video_embed": {
                                "vector": embedding,
                                "k": 1,
                            }
                        }
                    },
                    "size": 1
                })
            ])
        
        # Add newline character after each line
        bulk_body = "\n".join(bulk_body) + "\n"

        headers = {
            "Content-Type": "application/x-ndjson"
        }

        timeout = 30
        try:
            async with session.post(f"{url}/_msearch", data=bulk_body, headers=headers, timeout=timeout) as response:
                if response.status == 200:
                    result = await response.json()
                    return self.process_results(result, embeddings)
                else:
                    print(f"Error: {response.status}, {await response.text()}")
                    return res
        except asyncio.TimeoutError:
            print(f"Timeout in get_similarity_score")
        except aiohttp.ClientConnectorError as e:
            print(f"Error connecting to DB: {e}")
        except Exception as e:
            print(f"Error getting similarity score: {e}")
            if not self.is_down:
                traceback.print_exc()
        # should not get here if everything is ok
        return res
        
            

    def process_results(self, result, embeddings):
        processed_results = []
        for response, embedding in zip(result['responses'], embeddings):
            if response and ('hits' in response) and response['hits']['hits']:
                top_hit = response['hits']['hits'][0]
                similarity = F.cosine_similarity(
                    torch.tensor(embedding).unsqueeze(0),
                    torch.tensor(top_hit["_source"]["video_embed"]).unsqueeze(0)
                ).tolist()[0]

                processed_results.append(similarity)
            else:
                if 'error' in response:
                    print(f"Rejected by DB with status code: {response['status']}")
                else:
                    print(response)
                    print(f"No search results in db, novelty must be high in this case.")
                processed_results.append(None)
                continue
            
        return processed_results

    async def get_similarity_score(self, session, url, embedding):
        data = {
            "query": {
                "knn": {
                    "video_embed": {
                        "vector": embedding,
                        "k": 1,
                    },
                },
            },
            "size": 1,
        }
        timeout = 30
        try:
            async with session.post(url, json=data, timeout=timeout) as response:
                if response.status != 200:
                    text = await response.text()
                    print(f"Error getting similarity score: [{response.status}] {text}")
                    return None
                top_hit = ((await response.json())["hits"]["hits"] or [None])[0]
                if not top_hit:
                    print(f"No search results in db, novelty must be high in this case.")
                    return 0
                similarity = F.cosine_similarity(
                    torch.tensor(embedding).unsqueeze(0),
                    torch.tensor(top_hit["_source"]["video_embed"]).unsqueeze(0)
                ).tolist()[0]

                return similarity
        except asyncio.TimeoutError:
            print(f"Timeout in get_similarity_score")
        except aiohttp.ClientConnectorError as e:
            print(f"Error connecting to DB: {e}")
        except Exception as e:
            print(f"Error getting similarity score: {e}")
            if not self.is_down:
                traceback.print_exc()
        # should not get here if everything is ok
        return None
    

    async def get_similarity_scores(self, embeddings):
        scores = []
        similarity_sentinel = 2
        # if db is down, give it UPTIME_CHECK_INTERVAL s to recover and don't send any requests to db
        if self.is_down and ((time.time() - self.last_uptime_check_time) < self.UPTIME_CHECK_INTERVAL):
            return [similarity_sentinel] * len(embeddings)
        url=f"{self.url}/{self.index_name}/_search"
        async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.username, self.password),
                                         connector=aiohttp.TCPConnector(ssl=False)) as session:
            results = await self.bulk_knn_search(session, self.url, self.index_name, embeddings)
            scores = [r if r is not None else similarity_sentinel for r in results]

            if sum(scores) >= similarity_sentinel * len(scores):
                print(f"DB is down: {scores}")
                if not self.is_down:
                    self.is_down = True
                    #send_telegram_message(f"Vector DB {self.name} is down.")
                elif (time.time() - self.last_uptime_check_time) > self.UPTIME_CHECK_INTERVAL:
                    send_telegram_message(f"Vector DB {self.name} is down for >{self.UPTIME_CHECK_INTERVAL} s. Restarting.")
                    restart_pm2()
            else:
                if self.is_down and ((time.time() - self.last_uptime_check_time) > self.UPTIME_CHECK_INTERVAL) and similarity_sentinel not in scores:
                    self.is_down = False
                    print(f"DB is up")
                    #send_telegram_message(f"Vector DB {self.name} is up.")

            self.last_uptime_check_time = time.time()

        return scores


def send_telegram_message(message):
    send_text = ('https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage?chat_id=' + TELEGRAM_CHAT_ID +
                 '&text=' + message)
    retry = 0
    while retry < 5:
        try:
            print(f"Sending TG message: {message}")
            response = requests.get(send_text)
            print(response)
            break
        except Exception as e:
            retry += 1
            print(e)
