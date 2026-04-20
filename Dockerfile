FROM python:3-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telewatcher.py .
COPY prompts/ prompts/

# config.yaml and session file are expected to be mounted at runtime
VOLUME ["/data"]

ENV CONFIG_PATH=/data/config.yaml

CMD ["sh", "-c", "python telewatcher.py ${CONFIG_PATH}"]
