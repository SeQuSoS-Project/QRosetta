FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY runners/quimb-runner/requirements.txt .
COPY runners/quimb-runner/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir -r requirements.lock

# Copy shared models/helpers
COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY runners/quimb-runner/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ENV HOME=/home/appuser
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
