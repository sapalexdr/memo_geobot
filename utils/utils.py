import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv.main import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    filename='utils/bot.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv()

BOT_API_TOKEN = os.getenv("BOT_API_TOKEN")

storage = MemoryStorage()
bot = Bot(token=BOT_API_TOKEN)
dp = Dispatcher(bot, storage=storage)

ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))

NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
NOTION_DB = os.getenv('NOTION_DB')


class UserStates(StatesGroup):
    street_search = State()
