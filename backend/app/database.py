import motor.motor_asyncio
from app.config import settings
from app.core.logging import get_logger

# Async MongoDB client — single instance shared across app lifecycle
client = motor.motor_asyncio.AsyncIOMotorClient(
    settings.MONGODB_URI,
    serverSelectionTimeoutMS=5000
)

db = client[settings.MONGODB_DB_NAME]

# Collections
users_collection = db["users"]
documents_collection = db["documents"]
refresh_tokens_collection = db["refresh_tokens"]
query_logs_collection = db["query_logs"]


async def create_indexes():
    # No‑op: index creation is skipped in in‑memory mode.
    return

async def ping_db():
    """Health check – always returns True in demo mode (no DB)."""
    return True
