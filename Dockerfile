FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y pkg-config && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure upload directories exist
RUN mkdir -p static/uploads static/attachments

EXPOSE 5000

# Run with Gunicorn in production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
