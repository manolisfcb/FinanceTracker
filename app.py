from src import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=app.config.get("HOST") or "127.0.0.1",
        # Not 5000: macOS AirPlay Receiver (ControlCenter) listens on *:5000
        # and wins over a 127.0.0.1 bind, so the app answers 403 AirTunes.
        port=int(app.config.get("PORT") or 5001),
        debug=app.config.get("DEBUG", False),
    )
