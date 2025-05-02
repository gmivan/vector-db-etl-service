#!/bin/bash
# Restart the OpenSearch Docker container twice with a 30-second wait time in between
pm2 stop db_service_server -k 30000
pm2 stop etl_pipeline -k 30000

# Wait for processes to stop
sleep 5

# Start services
pm2 start db_service_server
pm2 start etl_pipeline

# Show logs
pm2 logs
