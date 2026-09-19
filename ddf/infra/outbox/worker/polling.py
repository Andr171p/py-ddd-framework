import asyncio
import logging

from .config import OutboxWorkerConfig
from .types import ProcessorFactory

logger = logging.getLogger(__name__)


async def run_polling_worker(processor_factory: ProcessorFactory, config: OutboxWorkerConfig) -> None:
    while True:
        # noinspection PyBroadException
        try:
            async with processor_factory() as processor:
                processed = await processor.process()
        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Outbox processing failed.")
            await asyncio.sleep(config.error_interval)
            continue

        if processed == 0:
            await asyncio.sleep(config.poll_interval)
