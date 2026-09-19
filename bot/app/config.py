import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000/api/v1")
BOT_INTERNAL_SECRET = os.environ["BOT_INTERNAL_SECRET"]
