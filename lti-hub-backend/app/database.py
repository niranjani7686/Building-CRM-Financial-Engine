import os
from motor.motor_asyncio import AsyncIOMotorClient

# Get MongoDB URI and database name from environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "p5_crm")

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect_db(cls):
        """Establish connection to MongoDB."""
        cls.client = AsyncIOMotorClient(MONGO_URI)
        cls.db = cls.client[DB_NAME]
        print(f"Connected to MongoDB at {MONGO_URI}, database: {DB_NAME}")

    @classmethod
    async def close_db(cls):
        """Close connection to MongoDB."""
        if cls.client:
            cls.client.close()
            print("MongoDB connection closed.")

    @classmethod
    def get_collection(cls, name: str):
        """Get a collection by name from the database."""
        if cls.db is None:
            # Fallback initialization for testing or direct usage
            cls.client = AsyncIOMotorClient(MONGO_URI)
            cls.db = cls.client[DB_NAME]
        return cls.db[name]

# Helper function to get collections directly
def get_proposals_collection():
    return Database.get_collection("p5_proposals")

def get_quotations_collection():
    return Database.get_collection("p5_quotations")

def get_invoices_collection():
    return Database.get_collection("p5_invoices")

def get_payments_collection():
    return Database.get_collection("p5_payments")

def get_client_projects_collection():
    return Database.get_collection("p5_client_projects")
