from flask import Flask

from index import chatbot_bp

app = Flask(__name__)
app.register_blueprint(chatbot_bp)
