from unittest.mock import MagicMock

from src import _is_reloader_parent


def _app(debug: bool):
    app = MagicMock()
    app.debug = debug
    return app


def test_debug_watcher_process_does_not_start_the_scheduler(monkeypatch):
    monkeypatch.delenv('WERKZEUG_RUN_MAIN', raising=False)

    assert _is_reloader_parent(_app(debug=True)) is True


def test_the_reloaded_child_process_does_start_it(monkeypatch):
    monkeypatch.setenv('WERKZEUG_RUN_MAIN', 'true')

    assert _is_reloader_parent(_app(debug=True)) is False


def test_production_has_no_reloader_so_it_always_starts(monkeypatch):
    monkeypatch.delenv('WERKZEUG_RUN_MAIN', raising=False)

    assert _is_reloader_parent(_app(debug=False)) is False
