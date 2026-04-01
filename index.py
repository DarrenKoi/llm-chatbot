from api import create_application

application = create_application()

if __name__ == "__main__":
    application.run(host="0.0.0.0", debug=True)
