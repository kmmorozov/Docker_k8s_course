import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "My App v%s" % os.environ.get("APP_VERSION", "dev")

@app.route("/health")   # livenessProbe
def health():
    return "ok", 200

@app.route("/ready")    # readinessProbe
def ready():
    return "ready", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
