workers = 1
worker_class = "gunicorn_utils.MyUvicornWorker" #"uvicorn_worker.UvicornWorker"
preload_app = False
bind = "0.0.0.0:8771"
wsgi_app = "db_service_server:app"