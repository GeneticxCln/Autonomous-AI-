FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

ENV ENVIRONMENT=production \
    API_DEBUG=false

# Run DB migrations then start API
CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn agent_system.fastapi_app:app --host 0.0.0.0 --port 8000"]
