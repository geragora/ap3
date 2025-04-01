from locust import HttpUser, task, between
import random
import string


def random_alias():
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))


def random_url():
    return "https://example.com/" + \
        "".join(random.choices(string.ascii_letters, k=5))


class LinkShortenerUser(HttpUser):
    wait_time = between(1, 3)  # Задержка между запросами

    @task
    def create_short_link(self):
        self.client.post(
            "/links/shorten",
            json={"original_url": random_url(), "custom_alias": random_alias()}
        )

    @task
    def get_original_url(self):
        short_code = "s3"  # Можно сделать динамическим
        self.client.get(f"/links/{short_code}")
