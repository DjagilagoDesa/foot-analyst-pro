FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py engine.py analysis_report.py accounts.py init_accounts.py profile.js custom-ticket.js daily-tickets.js account-deletion.html index.html manifest.webmanifest icon.svg stadium.jpg stade_premium.png ./
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "python init_accounts.py && gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 90 app:app"]

