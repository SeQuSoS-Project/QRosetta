FROM python:3.10-slim@sha256:4ba18b066cee17f2696cf9a2ba564d7d5eb05a91d6a949326780aa7c6912160d

RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY runners/pyquil-runner/requirements.txt .
COPY runners/pyquil-runner/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir -r requirements.lock

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY runners/pyquil-runner/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ENV HOME=/home/appuser
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
