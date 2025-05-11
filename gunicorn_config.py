"""
Gunicorn configuration file for deployment on Render
"""

import multiprocessing

# Gunicorn configuration
bind = "0.0.0.0:$PORT"  # Bind to the port provided by Render
workers = multiprocessing.cpu_count() * 2 + 1  # Recommended number of workers
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"  # Use gevent for WebSockets
timeout = 120  # Increase timeout to 120 seconds
keepalive = 5  # Keep-alive timeout
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log errors to stdout
loglevel = "info"  # Log level
