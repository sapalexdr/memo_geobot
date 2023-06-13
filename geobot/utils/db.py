import logging
import os

from dotenv.main import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

DB_USER_NAME = os.getenv("DB_USER_NAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


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
                f"mongodb+srv://{DB_USER_NAME}:{DB_PASSWORD}@cluster0.nq2ja1q.mongodb.net/?retryWrites=true&w=majority"
            )
            logging.info("Connected to MongoDB")
        except Exception as e:
            logging.error("Failed to connect to MongoDB: %s", e)
            raise e

    async def get_collection(self, db_name, collection_name):
        db = self.client[db_name]
        collection = db[collection_name]
        return collection

    async def close(self):
        self.client.close()
