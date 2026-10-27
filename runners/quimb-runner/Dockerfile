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
    chmod -R g=u,o=rX /home/appuser
ENV HOME=/home/appuser
COPY runners/quimb-runner/Dockerfile runners/quimb-runner/requirements.lock /usr/local/share/qrosetta-build/
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ARG QROSETTA_IMAGE_SOURCE=unknown
ARG QROSETTA_RELEASE=
RUN mkdir -p /usr/local/share/qrosetta-image \
    && printf 'source=%s\nrelease=%s\ngit_sha=%s\n' "$QROSETTA_IMAGE_SOURCE" "$QROSETTA_RELEASE" "$QROSETTA_GIT_SHA" \
       > /usr/local/share/qrosetta-image/identity
USER appuser

CMD ["sh", "-c", "exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
