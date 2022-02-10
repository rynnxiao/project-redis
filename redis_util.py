import redis
import random
import time

NAME = ["cheng", "siyi", "junxi", "linxi"]
TOP_NUM = 2
TOPIC = "Score"

def gen_data(redis_instance):
    name = random.choice(NAME)
    redis_instance.hincrby(TOPIC, name, random.randint(-3,5))

def run():
    redis_instance = redis.Redis(host="localhost")
    for _ in range(10000):
        gen_data(redis_instance)
        time.sleep(0.1)

if __name__ == "__main__":
    run()