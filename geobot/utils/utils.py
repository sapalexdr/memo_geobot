import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv.main import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LEVEL")
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  level=LOG_LEVEL)


BOT_API_TOKEN = os.getenv("BOT_API_TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))

storage = MemoryStorage()
bot = Bot(token=BOT_API_TOKEN)
dp = Dispatcher(bot, storage=storage)

class UserStates(StatesGroup):
    street_search = State()

NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
NOTION_DB = os.getenv('NOTION_DB')
