import logging
import os

from dotenv.main import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

DB_USER_NAME = os.getenv("DB_USER_NAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class MongoDB(metaclass=SingletonMeta):
    def __init__(self):
        self.client = None

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(
                f"mongodb+srv://{DB_USER_NAME}:{DB_PASSWORD}@{DB_HOST}/?retryWrites=true&w=majority"
            )
            logging.info("Connected to MongoDB")
        except Exception as e:
            logging.error("Failed to connect to MongoDB: %s", e)
            raise e

    async def get_collection(self, collection_name):
        db = self.client[DB_NAME]
        collection = db[collection_name]
        return collection

    async def close(self):
        self.client.close()
