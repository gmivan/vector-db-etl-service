# ==============================================================================
# Workaround to avoid "Error while closing socket [Errno 9] Bad file descriptor"
# while sending SIGHUP to gunicorn for graceful restart
# https://github.com/benoitc/gunicorn/issues/1877#issuecomment-1911136399
from uvicorn_worker import UvicornWorker
MyUvicornWorker = UvicornWorker
MyUvicornWorker.CONFIG_KWARGS = {"loop": "asyncio", "http": "auto"}
# ==============================================================================
