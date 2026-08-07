FLASK_APP=app:create_app

# Debug mode is DEVELOPMENT ONLY. The Werkzeug debugger exposes an interactive
# Python console on any unhandled exception, which is remote code execution if
# it is ever reachable in production. Gunicorn ignores this file, but do not
# set FLASK_DEBUG in .env or in Render's environment.
FLASK_DEBUG=1
