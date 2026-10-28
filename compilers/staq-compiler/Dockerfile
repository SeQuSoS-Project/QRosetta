ARG STAQ_VERSION=3.5
ARG STAQ_SHA256=838402b6ca541200740cc3ab989b3026f3b001ebf3e1ce7d89ae7f09a0e33195
ARG STAQ_CXXFLAGS="-std=c++17 -O2 -DNDEBUG -DUSE_OPENQASM2_SPECS=false"

FROM python:3.13-slim@sha256:aaf08c5490d52cd92bc27142a5215b1e47355a5eaf9adfad2a0fbc022d0b5490 AS staq-build

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT=20261020T213255Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${DEBIAN_SNAPSHOT}\$" /etc/apt/sources.list.d/debian.sources)" = 2

ARG STAQ_VERSION
ARG STAQ_SHA256
ARG STAQ_CXXFLAGS
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -sSL -o staq.tar.gz "https://github.com/softwareQinc/staq/archive/refs/tags/v${STAQ_VERSION}.tar.gz" \
    && echo "${STAQ_SHA256}  staq.tar.gz" | sha256sum -c - \
    && tar xzf staq.tar.gz \
    && cd "staq-${STAQ_VERSION}" \
    && g++ ${STAQ_CXXFLAGS} -DSTAQ_VERSION_STR="\"${STAQ_VERSION}\"" \
        -Iinclude -Iqasmtools/include -isystem libs -isystem libs/third_party \
        src/staq/main.cpp -o /build/staq-bin -pthread

FROM python:3.13-slim@sha256:aaf08c5490d52cd92bc27142a5215b1e47355a5eaf9adfad2a0fbc022d0b5490

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT=20261020T213255Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${DEBIAN_SNAPSHOT}\$" /etc/apt/sources.list.d/debian.sources)" = 2

ARG STAQ_VERSION
ARG STAQ_SHA256
ARG STAQ_CXXFLAGS
RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY --from=staq-build /build/staq-bin /usr/local/bin/staq
COPY compilers/staq-compiler/requirements.txt .
COPY compilers/staq-compiler/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY shared /tmp/shared-src
RUN pip install --no-cache-dir --no-deps --no-build-isolation --no-index /tmp/shared-src && \
    rm -rf /tmp/shared-src

COPY compilers/staq-compiler/Dockerfile compilers/staq-compiler/requirements.lock /usr/local/share/qrosetta-build/
COPY compilers/staq-compiler/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u,o=rX /home/appuser
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ARG QROSETTA_IMAGE_SOURCE=unknown
ARG QROSETTA_RELEASE=
RUN mkdir -p /usr/local/share/qrosetta-image \
    && printf 'source=%s\nrelease=%s\ngit_sha=%s\n' "$QROSETTA_IMAGE_SOURCE" "$QROSETTA_RELEASE" "$QROSETTA_GIT_SHA" \
       > /usr/local/share/qrosetta-image/identity
ENV PYTHONHASHSEED=0
ENV STAQ_VERSION=${STAQ_VERSION} \
    STAQ_SHA256=${STAQ_SHA256} \
    STAQ_CXXFLAGS=${STAQ_CXXFLAGS}
USER appuser

CMD ["sh", "-c", "exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
