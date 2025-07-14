FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
ENV FLASK_APP=app:app
ENV FLASK_ENV=production
CMD ["sh", "-c", "flask db upgrade && flask run --host=0.0.0.0 --port=8001"]
