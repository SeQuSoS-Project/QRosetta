FROM python:3.10-slim

RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY runners/qibo-runner/requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY runners/qibo-runner/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ENV HOME=/home/appuser
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
