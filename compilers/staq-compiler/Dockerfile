FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634 AS staq-build

ARG STAQ_VERSION=3.5
ARG STAQ_SHA256=838402b6ca541200740cc3ab989b3026f3b001ebf3e1ce7d89ae7f09a0e33195
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -sSL -o staq.tar.gz "https://github.com/softwareQinc/staq/archive/refs/tags/v${STAQ_VERSION}.tar.gz" \
    && echo "${STAQ_SHA256}  staq.tar.gz" | sha256sum -c - \
    && tar xzf staq.tar.gz \
    && cd "staq-${STAQ_VERSION}" \
    && g++ -std=c++17 -O2 -DNDEBUG -DSTAQ_VERSION_STR="\"${STAQ_VERSION}\"" -DUSE_OPENQASM2_SPECS=false \
        -Iinclude -Iqasmtools/include -isystem libs -isystem libs/third_party \
        src/staq/main.cpp -o /build/staq-bin -pthread

FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634

RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY --from=staq-build /build/staq-bin /usr/local/bin/staq
COPY compilers/staq-compiler/requirements.txt .
COPY compilers/staq-compiler/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir -r requirements.lock

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY compilers/staq-compiler/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ENV STAQ_VERSION=3.5
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
