# simple_flask_application.py
#
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "<h1>Hello from Flask!</h1>\n"

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)

################

