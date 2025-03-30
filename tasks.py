import asyncio
from datetime import datetime, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from db import Link

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/urls"
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from sqlalchemy import text

async def delete_unused_links_async():
    async with async_session_maker() as session:
        N_MINUTES = 10 
        threshold_date = datetime.utcnow() - timedelta(minutes=N_MINUTES)

        logger.info(f"Ищем ссылки, не использовавшиеся с {threshold_date}...")

        try:
            result = await session.execute(
                select(Link.short_code).where(Link.last_used_at < threshold_date).where(Link.last_used_at.isnot(None))
            )
            short_codes_to_delete = result.scalars().all()

            logger.info(f"Найдено {len(short_codes_to_delete)} ссылок для удаления: {short_codes_to_delete}")

            if not short_codes_to_delete:
                logger.info("Нет ссылок для удаления.")
                return

            delete_query = text(
                "DELETE FROM links WHERE short_code = ANY(:codes)"
            )
            await session.execute(delete_query, {'codes': short_codes_to_delete})

            await session.commit()

            logger.info(f"Удалено {len(short_codes_to_delete)} ссылок.")
        except Exception as e:
            logger.error(f"Ошибка при удалении ссылок: {e}")



from celery import Celery

celery_app = Celery('tasks', broker='pyamqp://guest@localhost//')

@celery_app.task
def delete_unused_links():
    logger.info("Запуск задачи очистки ссылок...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(delete_unused_links_async()) 