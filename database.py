import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()  # Load .env file

MONGO_URI = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)
db = client["Shopcart"]  # Your DB name in MongoDB Atlas

cart_collection = db["carts"]
products_collection = db["products"]
users_collection = db["users"]
orders_collection = db["orders"]


import asyncio

async def check_db_connection():
    try:
        # The ping command is cheap and does not require auth
        await client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")

if __name__ == "__main__":
    asyncio.run(check_db_connection())
