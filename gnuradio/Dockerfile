FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fm_failover.py .

EXPOSE 8080

CMD ["python", "fm_failover.py", "--active=FM1"]