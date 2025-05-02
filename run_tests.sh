#!/bin/bash

# Exit on any error
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BLUE='\033[0;34m'

# Print with timestamp
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Check if python/pip is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed${NC}"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}Error: pip3 is not installed${NC}"
    exit 1
fi

# Check if virtualenv exists, if not create it
if [ ! -d "venv" ]; then
    log "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
log "Activating virtual environment..."
source venv/bin/activate

# Install requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    log "Installing requirements..."
    pip install -r requirements.txt
else
    log "Installing required packages..."
    pip install pytest pytest-asyncio aiohttp python-dotenv numpy requests
fi

# Check if .env file exists, if not create it with default values
if [ ! -f ".env" ]; then
    log "Creating default .env file..."
    cat > .env << EOL
API_URL=http://127.0.0.1:14920
INDEX_NAME=omega
USERNAME=admin
OPENSEARCH_PASSWORD=admin
EOL
fi

# Run the tests
log "Running tests..."
python -m pytest test_etl.py -v

# Check test result
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed successfully!${NC}"
else
    echo -e "\n${RED}Some tests failed!${NC}"
    exit 1
fi 