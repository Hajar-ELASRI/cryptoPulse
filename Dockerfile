FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY collectors ./collectors
COPY sentiment ./sentiment
COPY scripts/__init__.py scripts/historical_loader.py ./scripts/
ENV PYTHONUNBUFFERED=1

