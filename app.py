from src import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=app.config.get("HOST") or "127.0.0.1",
        port=int(app.config.get("PORT") or 5000),
        debug=app.config.get("DEBUG", False),
    )
