"""
### Алгоритм

connect + LISTEN
      ↓
process()
      ↓
processed > 0?
 ├─ yes → process immediately again
 │
 └─ no
      ↓
wait NOTIFY
   or timeout
      ↓
process()
"""


import asyncio
import logging

from ddf.infra.outbox.worker.config import OutboxWorkerConfig
from ddf.infra.outbox.worker.types import ProcessorFactory

from .outbox_listener import PostgresOutboxListener

logger = logging.getLogger(__name__)


async def run_postgres_notify_worker(
    processor_factory: ProcessorFactory,
    listener: PostgresOutboxListener,
    config: OutboxWorkerConfig,
) -> None:
    while True:
        # noinspection PyBroadException
        try:
            async with listener:
                while True:
                    async with processor_factory() as processor:
                        processed = await processor.process()

                    if processed > 0:
                        continue

                    await listener.wait(timeout=config.poll_interval)
        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("PostgreSQL outbox worker failed.")
            await asyncio.sleep(config.error_interval)
