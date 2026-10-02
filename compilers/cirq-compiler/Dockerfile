FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634

RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY compilers/cirq-compiler/requirements.txt .
COPY compilers/cirq-compiler/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir -r requirements.lock

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY compilers/cirq-compiler/Dockerfile compilers/cirq-compiler/requirements.lock /usr/local/share/qrosetta-build/
COPY compilers/cirq-compiler/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ENV HOME=/home/appuser
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ENV PYTHONHASHSEED=0
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
