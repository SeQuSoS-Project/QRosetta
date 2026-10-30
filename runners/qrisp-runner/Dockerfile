FROM python:3.12-slim@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT=20261020T213255Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${DEBIAN_SNAPSHOT}\$" /etc/apt/sources.list.d/debian.sources)" = 2

RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY runners/qrisp-runner/requirements.txt .
COPY runners/qrisp-runner/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Copy shared models/helpers
COPY shared /tmp/shared-src
RUN pip install --no-cache-dir --no-deps --no-build-isolation --no-index /tmp/shared-src && \
    rm -rf /tmp/shared-src

COPY runners/qrisp-runner/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u,o=rX /home/appuser
ENV HOME=/home/appuser
COPY runners/qrisp-runner/Dockerfile runners/qrisp-runner/requirements.lock /usr/local/share/qrosetta-build/
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ARG QROSETTA_IMAGE_SOURCE=unknown
ARG QROSETTA_RELEASE=
RUN mkdir -p /usr/local/share/qrosetta-image \
    && printf 'source=%s\nrelease=%s\ngit_sha=%s\n' "$QROSETTA_IMAGE_SOURCE" "$QROSETTA_RELEASE" "$QROSETTA_GIT_SHA" \
       > /usr/local/share/qrosetta-image/identity
USER appuser

CMD ["sh", "-c", "exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
