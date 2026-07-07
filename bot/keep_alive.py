from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is online and awake on port 8081!"

def run():
    # Explicitly binding to all interfaces on port 8081
    app.run(host='0.0.0.0', port=8081)

def keep_alive():
    """Starts the Flask server on a separate background thread so it doesn't block the Discord bot."""
    t = Thread(target=run)
    t.start()
