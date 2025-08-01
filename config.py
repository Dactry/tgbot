import os
from dotenv import load_dotenv

load_dotenv()  # завантажує змінні з .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))