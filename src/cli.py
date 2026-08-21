"""Deploy-time database commands.

`flask bootstrap-db` exists because this project's Alembic history cannot
build a schema from nothing: the migrations that create `users`, `assets`,
`transactions` and `categories` were never written (those tables came from an
early `db.create_all()`), and revision 4aaf4c55eabb then tries to alter a
`stocks` table nobody creates. A plain `flask db upgrade` against an empty
database dies on the second revision.

So the bootstrap branches on what it finds:

  * empty database  -> `db.create_all()` from the models, then stamp head, so
    Alembic agrees the schema is current and future migrations apply cleanly.
  * existing database with an alembic_version row -> `flask db upgrade`, the
    normal path.

Squashing the history into one real baseline migration is the proper fix and
would let this command go away; until then this is what makes a fresh
container able to start.
"""

import signal
import threading

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_migrate import stamp, upgrade
from sqlalchemy import inspect

from src.extensions import db


def register_cli(app):
    app.cli.add_command(bootstrap_db)
    app.cli.add_command(run_scheduler)


@click.command("bootstrap-db")
@with_appcontext
def bootstrap_db():
    """Bring the database to the current schema, whatever state it is in."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    if "alembic_version" in tables:
        click.echo(f"Base existente ({len(tables)} tablas) — aplicando migraciones pendientes.")
        upgrade()
        click.echo("Migraciones al día.")
        return

    # No Alembic bookkeeping: either a brand-new database, or one built by
    # create_all() before migrations existed. create_all() is idempotent, so
    # both cases are safe here.
    if tables:
        click.echo(f"Base sin historial de Alembic ({len(tables)} tablas) — completando y sellando.")
    else:
        click.echo("Base vacía — creando el esquema desde los modelos.")

    # Importing the package registers every mapper; without it create_all()
    # would only see whichever models happened to be imported already.
    import src.models  # noqa: F401

    db.create_all()
    stamp(revision="head")

    created = set(inspect(db.engine).get_table_names())
    click.echo(f"Esquema listo: {len(created)} tablas, selladas en head.")
    current_app.logger.info("bootstrap-db completed with %d tables", len(created))


@click.command("run-scheduler")
@with_appcontext
def run_scheduler():
    """Run only the scheduled jobs, and nothing else.

    The worker container's whole job. create_app() has already started
    APScheduler by the time this runs (RUN_SCHEDULER is on in that container),
    but APScheduler's threads are daemons: without something holding the main
    thread the process would exit immediately and the container would restart
    in a loop.
    """
    from src.extensions import scheduler

    if not current_app.config.get("RUN_SCHEDULER"):
        raise click.ClickException(
            "RUN_SCHEDULER está apagado — este proceso no tendría ningún job que correr."
        )

    jobs = scheduler.get_jobs()
    click.echo(f"Scheduler activo con {len(jobs)} jobs:")
    for job in jobs:
        click.echo(f"  - {job.id}: próxima ejecución {job.next_run_time}")

    stop = threading.Event()

    def _shutdown(signum, _frame):
        # Docker sends SIGTERM on `stop`; without handling it the container
        # waits out the full grace period and gets SIGKILLed mid-job.
        click.echo(f"Señal {signum} recibida — cerrando el scheduler.")
        stop.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    stop.wait()
    scheduler.shutdown(wait=True)
    click.echo("Scheduler detenido limpiamente.")
