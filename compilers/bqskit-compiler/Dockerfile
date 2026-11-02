FROM python:3.13-slim@sha256:aaf08c5490d52cd92bc27142a5215b1e47355a5eaf9adfad2a0fbc022d0b5490

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

COPY compilers/bqskit-compiler/requirements.txt .
COPY compilers/bqskit-compiler/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY shared /tmp/shared-src
# pip is not used at run time; uninstalling it removes the packages it vendors.
RUN pip install --no-cache-dir --no-deps --no-build-isolation --no-index /tmp/shared-src && \
    rm -rf /tmp/shared-src && \
    python -m pip uninstall --yes pip

COPY compilers/bqskit-compiler/Dockerfile compilers/bqskit-compiler/requirements.lock /usr/local/share/qrosetta-build/
COPY compilers/bqskit-compiler/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u,o=rX /home/appuser
ENV HOME=/home/appuser
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ARG QROSETTA_IMAGE_SOURCE=unknown
ARG QROSETTA_RELEASE=
RUN mkdir -p /usr/local/share/qrosetta-image \
    && printf 'source=%s\nrelease=%s\ngit_sha=%s\n' "$QROSETTA_IMAGE_SOURCE" "$QROSETTA_RELEASE" "$QROSETTA_GIT_SHA" \
       > /usr/local/share/qrosetta-image/identity
ENV PYTHONHASHSEED=0
USER appuser

CMD ["sh", "-c", "exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
