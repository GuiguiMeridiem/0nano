import os
from dotenv import load_dotenv

load_dotenv()

FAL_API_KEY = os.getenv("FAL_KEY")
FAL_QUEUE_BASE_URL = "https://queue.fal.run"
FAL_SYNC_BASE_URL = "https://fal.run"

if not FAL_API_KEY:
    raise EnvironmentError("FAL_KEY is not set. Add it to your .env file.")
