from redis import Redis
import os

class RedisClient:
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 0))
        self.client = Redis(host=self.redis_host, port=self.redis_port, db=self.redis_db)

    def set_value(self, key, value):
        self.client.set(key, value)

    def get_value(self, key):
        return self.client.get(key)

    def delete_value(self, key):
        self.client.delete(key)

    def exists(self, key):
        return self.client.exists(key) > 0

    def close(self):
        self.client.close()