from flask import Flask, Markup, render_template
from flask.wrappers import Response
import redis
import json 
import datetime
import time
from config import CRYPTO_CHANGE, CRYPTO_VOL, PRODUCTS, SCORE

app = Flask(__name__, template_folder='.')
REDIS_INST = redis.Redis(host="localhost")

TOP_NUM = -1


def get_data(redis_instance, topic, reset=False):
    while True:
        data = redis_instance.hgetall(topic)
        if reset:
            reset_data = {item:0 for item in PRODUCTS}
            redis_instance.hmset(topic, reset_data)
        json_data = json.dumps(
            {
                "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "label": [item.decode("utf-8")  for item in data],
                "value": [float(item.decode("utf-8"))  for item in data.values()]
            }
        )
        yield f"data:{json_data}\n\n"
        time.sleep(1)

@app.route("/")
def index():
    return render_template("index.html", title=f"{CRYPTO_CHANGE} Plot")

@app.route("/bar-data")
def bar_chart():
    return Response(
        get_data(REDIS_INST, CRYPTO_VOL, True),
        mimetype='text/event-stream'
        )

@app.route("/line-data")
def line_chart():
    return Response(
        get_data(REDIS_INST, SCORE),
        mimetype='text/event-stream'
        )


if __name__ == '__main__':
    app.run(debug=True)