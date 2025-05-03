# Vector DB ETL Service

A service for managing and monitoring video uniqueness using Qdrant vector database and Hugging Face datasets.

## Overview

This project provides a complete solution for:
- Monitoring Hugging Face datasets for new content
- Storing and managing video embeddings in a vector database
- Checking video uniqueness by comparing against existing content
- Providing a REST API for video similarity queries

## Architecture

The system consists of four main components:

1. **ETL Pipeline (`etl_pipeline.py`)**
   - Monitors Hugging Face datasets for new content
   - Processes and transforms data into embeddings
   - Updates the vector database with new content
   - Runs as a background service using PM2

2. **Database Service Server (`db_service_server.py`)**
   - FastAPI-based REST API server
   - Handles requests for video similarity checks
   - Returns similarity scores for video uniqueness verification
   - Runs as a background service using PM2

3. **Qdrant Vector Database**
   - Stores and indexes video embeddings
   - Provides efficient similarity search capabilities
   - Runs in a Docker container

4. **Worker Service**
   - Handles database operations
   - Processes similarity queries
   - Runs in a Docker container

## Prerequisites

- Python 3.8+
- Node.js and PM2
- Docker and Docker Compose
- Virtual environment (recommended)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gmivan/vector-db-etl-service.git
cd vector-db-etl-service
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install PM2 globally:
```bash
npm install -g pm2
```

## Configuration
Configure PM2 services:
- `etl_pipeline.config.js` - ETL pipeline configuration
- `db_service_server.config.js` - API server configuration

## Running the Services

### Using Docker Compose

Start the Qdrant database and worker service:
```bash
docker-compose up -d
```

### Using PM2

Start the ETL pipeline and API server:
```bash
# Start both services
pm2 start etl_pipeline.config.js
pm2 start db_service_server.config.js

# View logs
pm2 logs
```

To restart all services:
```bash
./restart.sh
```

## API Endpoints

The API server provides the following endpoints:

- `POST /add` - Add a new video embedding
- `POST /bulk_add` - Add multiple video embeddings
- `POST /get_similarity_scores` - Get similarity scores for a video
- `POST /delete` - Delete a video embedding
- `POST /delete_all` - Delete all video embeddings
- `GET /health` - Health check endpoint

## Testing

Run the test suite:
```bash
./run_tests.sh
```

## Monitoring

- PM2 provides process monitoring and logging
- Use `pm2 logs` to view real-time logs
- Use `pm2 status` to check service status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
