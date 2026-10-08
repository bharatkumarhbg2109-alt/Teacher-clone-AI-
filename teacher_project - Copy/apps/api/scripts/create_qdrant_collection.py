"""Ensure the Qdrant collection exists."""
import asyncio

from app.services.vector_store import vector_store


async def main() -> None:
    await vector_store.ensure_collection()
    print("Qdrant collection ready:", vector_store.COLLECTION)


if __name__ == "__main__":
    asyncio.run(main())
