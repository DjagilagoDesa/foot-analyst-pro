"""Run once before Gunicorn, never create an ephemeral production account DB."""
import os
from app import app
from accounts import init_schema

if os.environ.get('DATABASE_URL'):
    init_schema(app)
    print('Persistent account tables ready.')
else:
    print('DATABASE_URL absent: accounts disabled; public fixtures remain available.')
