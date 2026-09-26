from collections.abc import Iterable

from pymongo.asynchronous.database import AsyncDatabase

from .mongo_base_model import MongoBaseModel


async def initialize_mongo_models(database: AsyncDatabase, models: Iterable[type[MongoBaseModel]]) -> None:
    """Инициализация моделей MongoDB, объявляет коллекции, создаёт индексы."""

    for model in models:
        collection = database.get_collection(model.__collection_name__)

        if model.__indexes__:
            await collection.create_indexes(list(model.__indexes__))
