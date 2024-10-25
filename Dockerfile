# Use an official Python runtime as a parent image
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt --no-cache-dir

CMD ["python", "bot.py"]