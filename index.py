from api import create_application

app = create_application()

if __name__ == "__main__":
    from api import config
    app.run(host="0.0.0.0", port=config.FLASK_PORT)
