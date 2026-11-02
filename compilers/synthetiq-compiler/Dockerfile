ARG SYNTHETIQ_COMMIT=59a0cc6942c9561033a762ced2c35ceab9b876c3
ARG SYNTHETIQ_SHA256=90d553544d13bca950ab47726b8543fffaaea2554e5edad6cd10b6090c7156d6
ARG SYNTHETIQ_CXXFLAGS="-std=c++17 -fopenmp -O2 -DEIGEN_NO_DEBUG"

FROM python:3.13-slim@sha256:aaf08c5490d52cd92bc27142a5215b1e47355a5eaf9adfad2a0fbc022d0b5490 AS synthetiq-build

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT=20261020T213255Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${DEBIAN_SNAPSHOT}\$" /etc/apt/sources.list.d/debian.sources)" = 2

ARG SYNTHETIQ_COMMIT
ARG SYNTHETIQ_SHA256
ARG SYNTHETIQ_CXXFLAGS
RUN apt-get update && apt-get install -y --no-install-recommends build-essential patch curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -sSL -o synthetiq.tar.gz "https://github.com/eth-sri/synthetiq/archive/${SYNTHETIQ_COMMIT}.tar.gz" \
    && echo "${SYNTHETIQ_SHA256}  synthetiq.tar.gz" | sha256sum -c - \
    && tar xzf synthetiq.tar.gz && mv "synthetiq-${SYNTHETIQ_COMMIT}" synthetiq
COPY compilers/synthetiq-compiler/max-runs.patch /build/
RUN cd synthetiq && patch -p1 < ../max-runs.patch \
    && mkdir -p bin build \
    && for src in synthetiq/*.cpp; do \
         case "$src" in synthetiq/main.cpp|synthetiq/main_resynth.cpp|synthetiq/comparison_generator.cpp) continue;; esac; \
         g++ ${SYNTHETIQ_CXXFLAGS} -I include/eigen-3.3.9/ -c "$src" -o "build/$(basename "$src" .cpp).o" || exit 1; \
       done \
    && g++ ${SYNTHETIQ_CXXFLAGS} -I include/eigen-3.3.9/ synthetiq/main.cpp build/*.o -o bin/main

FROM python:3.13-slim@sha256:aaf08c5490d52cd92bc27142a5215b1e47355a5eaf9adfad2a0fbc022d0b5490

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT=20261020T213255Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${DEBIAN_SNAPSHOT}\$" /etc/apt/sources.list.d/debian.sources)" = 2

ARG SYNTHETIQ_COMMIT
ARG SYNTHETIQ_SHA256
ARG SYNTHETIQ_CXXFLAGS
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY --from=synthetiq-build /build/synthetiq/bin/main /usr/local/bin/synthetiq
COPY --from=synthetiq-build /build/synthetiq/data/gates /usr/local/share/synthetiq/gates
COPY compilers/synthetiq-compiler/requirements.txt .
COPY compilers/synthetiq-compiler/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY shared /tmp/shared-src
# pip is not used at run time; uninstalling it removes the packages it vendors.
RUN pip install --no-cache-dir --no-deps --no-build-isolation --no-index /tmp/shared-src && \
    rm -rf /tmp/shared-src && \
    python -m pip uninstall --yes pip

COPY compilers/synthetiq-compiler/Dockerfile compilers/synthetiq-compiler/requirements.lock compilers/synthetiq-compiler/max-runs.patch /usr/local/share/qrosetta-build/
COPY compilers/synthetiq-compiler/main.py .

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
ENV SYNTHETIQ_COMMIT=${SYNTHETIQ_COMMIT} \
    SYNTHETIQ_SHA256=${SYNTHETIQ_SHA256} \
    SYNTHETIQ_CXXFLAGS=${SYNTHETIQ_CXXFLAGS} \
    OMP_NUM_THREADS=1
USER appuser

CMD ["sh", "-c", "exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
