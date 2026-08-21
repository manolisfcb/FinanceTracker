"""Gunicorn settings for the TrueNorth web container."""

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Sync workers: the views are short and database-bound, and yfinance/requests
# calls happen in the scheduler process, not here. Capped at 4 because the
# usual container gets 1-2 CPUs and (2*N)+1 on a 16-core build host would
# open a pointless number of database connections.
workers = int(os.getenv("WEB_CONCURRENCY", min((multiprocessing.cpu_count() * 2) + 1, 4)))
threads = int(os.getenv("WEB_THREADS", 2))
worker_class = "gthread"

# Cloudflare's own timeout is 100s; failing before it gives a real error page
# rather than Cloudflare's 524.
timeout = 60
graceful_timeout = 30
# Must exceed the proxy's idle keep-alive so the connection is never closed
# mid-request from our side.
keepalive = 65

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
# %({x-forwarded-for}i)s rather than %(h)s: behind Cloudflare every request
# appears to come from the proxy otherwise.
access_log_format = '%({x-forwarded-for}i)s "%(r)s" %(s)s %(b)s %(D)sus'

# preload_app stays OFF on purpose. The factory runs per worker, which is
# what keeps each worker's SQLAlchemy engine and its connections its own —
# preloading forks the pool and hands every worker the same sockets.
preload_app = False
