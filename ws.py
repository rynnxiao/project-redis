import sys
import time
import pymongo
import redis
from ws_client import WebsocketClient
from config import PRODUCTS

class MyWebsocketClient(WebsocketClient):
    def on_open(self):
        self.url = "wss://ws-feed.pro.coinbase.com/"
        self.products = PRODUCTS
        self.message_count = 0
        print("Let's count the messages!")

    def on_close(self):
        print("-- Goodbye! --")

if __name__ == "__main__":
    mongodb = pymongo.MongoClient("mongodb://localhost:27017/")
    mongodb_collection = {
        "snapshot": mongodb["coinbase"]["snapshot"], 
        "l2update": mongodb["coinbase"]["l2_data"], 
        "match": mongodb["coinbase"]["matches"], 
    }
    redis_collection = redis.Redis(host="localhost")

    wsClient = MyWebsocketClient(redis_collection=redis_collection, channels=["matches"])
    wsClient.start()
    print(wsClient.url, wsClient.products)
    try:
        while True:
            print("\nMessageCount =", "%i \n" % wsClient.message_count)
            time.sleep(1)
    except KeyboardInterrupt:
        wsClient.close()

    if wsClient.error:
        sys.exit(1)
    else:
        sys.exit(0)
