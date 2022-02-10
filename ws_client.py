
from __future__ import print_function
import json
import base64
import hmac
import hashlib
import time
from threading import Thread
from requests.auth import AuthBase
from websocket import create_connection
from config import CRYPTO, CRYPTO_CHANGE, CRYPTO_VOL

PASSPHARSE = ""
API_SECRET = ""
API_KEY = ""

def get_auth_headers(timestamp, message, api_key, secret_key, passphrase):
    message = message.encode('ascii')
    hmac_key = base64.b64decode(secret_key)
    signature = hmac.new(hmac_key, message, hashlib.sha256)
    signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')
    return {
        'Content-Type': 'Application/JSON',
        'CB-ACCESS-SIGN': signature_b64,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-ACCESS-KEY': api_key,
        'CB-ACCESS-PASSPHRASE': passphrase
    }


class WebsocketClient:
    def __init__(
            self,
            url="wss://ws-feed.pro.coinbase.com",
            products=None,
            message_type="subscribe",
            mongo_collection=None,
            redis_collection=None,
            should_print=True,
            auth=False,
            api_key=API_KEY,
            api_secret=API_SECRET,
            api_passphrase=PASSPHARSE,
            # Make channels a required keyword-only argument; see pep3102
            *,
            # Channel options: ['ticker', 'user', 'matches', 'level2', 'full']
            channels):
        self.url = url
        self.products = products
        self.channels = channels
        self.type = message_type
        self.stop = True
        self.error = None
        self.ws = None
        self.thread = None
        self.auth = auth
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.should_print = should_print
        self.mongo_collection = mongo_collection
        self.redis_collection = redis_collection

    def start(self):
        def _go():
            self._connect()
            self._listen()
            self._disconnect()

        self.stop = False
        self.on_open()
        self.thread = Thread(target=_go)
        self.keepalive = Thread(target=self._keepalive)
        self.thread.start()

    def _connect(self):
        if not self.products:
            self.products = ["BTC-USD"]
        elif not isinstance(self.products, list):
            self.products = [self.products]

        if self.url.endswith("/"):
            self.url = self.url[:-1]

        if not self.channels:
            self.channels = [{"name": "ticker", "product_ids": [product_id for product_id in self.products]}]
            sub_params = {'type': 'subscribe', 'product_ids': self.products, 'channels': self.channels}
        else:
            sub_params = {'type': 'subscribe', 'product_ids': self.products, 'channels': self.channels}

        if self.auth:
            timestamp = str(time.time())
            message = timestamp + 'GET' + '/users/self/verify'
            auth_headers = get_auth_headers(timestamp, message, self.api_key, self.api_secret, self.api_passphrase)
            sub_params['signature'] = auth_headers['CB-ACCESS-SIGN']
            sub_params['key'] = auth_headers['CB-ACCESS-KEY']
            sub_params['passphrase'] = auth_headers['CB-ACCESS-PASSPHRASE']
            sub_params['timestamp'] = auth_headers['CB-ACCESS-TIMESTAMP']

        self.ws = create_connection(self.url)

        self.ws.send(json.dumps(sub_params))

    def _keepalive(self, interval=30):
        while self.ws.connected:
            self.ws.ping("keepalive")
            time.sleep(interval)

    def _listen(self):
        self.keepalive.start()
        while not self.stop:
            try:
                data = self.ws.recv()
                msg = json.loads(data)
            except ValueError as e:
                self.on_error(e)
            except Exception as e:
                self.on_error(e)
            else:
                self.on_message(msg)

    def _disconnect(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception as e:
            pass
        finally:
            self.keepalive.join()

        self.on_close()

    def close(self):
        self.stop = True   # will only disconnect after next msg recv
        self._disconnect() # force disconnect so threads can join
        self.thread.join()

    def on_open(self):
        if self.should_print:
            print("-- Subscribed! --\n")

    def on_close(self):
        if self.should_print:
            print("\n-- Socket Closed --")

    def on_message(self, msg):
        if self.should_print:
            print(msg)
        if self.mongo_collection:  # dump JSON to given mongo collection
            if msg["type"] in self.mongo_collection:
                self.mongo_collection[msg["type"]].insert_one(msg)
        if self.redis_collection and "product_id" in msg:
            pre_price = self.redis_collection.hget(CRYPTO, msg["product_id"])
            self.redis_collection.hset(CRYPTO, msg["product_id"], msg["price"])
            self.redis_collection.hincrbyfloat(CRYPTO_VOL, msg["product_id"], msg["size"])
            if not pre_price:
                pre_price = msg["price"]
                self.redis_collection.hset(CRYPTO_CHANGE, f"{msg['product_id']}_change", 1)
            else:
                change_price = float(pre_price)/float(msg["price"]) - 1
                self.redis_collection.hincrbyfloat(CRYPTO_CHANGE, f"{msg['product_id']}_change", change_price)


    def on_error(self, e, data=None):
        self.error = e
        self.stop = True
        print('{} - data: {}'.format(e, data))

