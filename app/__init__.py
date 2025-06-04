from flask import Flask
from .server import bp, SECRET_KEY

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY
app.register_blueprint(bp)
