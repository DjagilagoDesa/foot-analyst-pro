FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py adaptive_history.py match_availability.py champions_context.py evaluation.py selection_test.py publication.py daily_opinion.py daily-opinion.js tracking.py engine.py analysis_report.py accounts.py init_accounts.py profile.js ticket-builder.js tracking.js custom-ticket.js daily-tickets.js account-deletion.html index.html manifest.webmanifest icon.svg stadium.jpg stade_premium.png ./
COPY personnel.js market_odds.py odds-ticket.js ./
COPY shadow_experiment.py opponent_benchmark.py opponent_review.py shadow_seed.json.gz ./
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "python init_accounts.py && gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 90 app:app"]




