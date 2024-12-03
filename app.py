import flask 
from flask import request, jsonify






app = flask.Flask(__name__)
app.config["DEBUG"] = True


@app.route('/', methods=['GET'])
def home():
    return "<h1>API</h1><p>This is an API for the project.</p>"

if __name__ == '__main__':
    app.run(debug=True)