FROM python:3.12-slim

WORKDIR /app
COPY . /app

EXPOSE 8765

CMD ["python3", "-m", "src.play", "--host", "0.0.0.0", "--port", "8765", "--no-open"]
