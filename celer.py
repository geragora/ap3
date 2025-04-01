from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "tasks",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
    include=["tasks"]
)

celery_app.conf.beat_schedule = {
    "delete-unused-links-every-minute": {
        "task": "tasks.delete_unused_links",
        "schedule": crontab(minute="*"),  # Запуск каждую минуту
    },
}

celery_app.conf.timezone = "UTC"
