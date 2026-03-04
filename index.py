from api import create_application

app = create_application()

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
