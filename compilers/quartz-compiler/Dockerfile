ARG QUARTZ_VERSION=0.3.2
ARG QUARTZ_SHA256=4563a45382ae6da3ed7528b73bee4472fa147c3f17133b9282ab1d6fb27e2dcc
ARG ECC_MAX_GATES=3
ARG ECC_SHA256=e68e9c41229a675e0e0b5dcb97716cc0c0e6ffe15fa2ade13aed6b01a1140d05
ARG QUARTZ_LIBRARY_CXXFLAGS="-include algorithm"
ARG QUARTZ_TOOL_CXXFLAGS="-std=c++17 -O2 -fopenmp -DUSE_RATIONAL"

FROM python:3.13-slim@sha256:aaf08c5490d52cd92bc27142a5215b1e47355a5eaf9adfad2a0fbc022d0b5490 AS quartz-build

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT=20261020T213255Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${DEBIAN_SNAPSHOT}\$" /etc/apt/sources.list.d/debian.sources)" = 2

ARG QUARTZ_VERSION
ARG QUARTZ_SHA256
ARG ECC_MAX_GATES
ARG ECC_SHA256
ARG QUARTZ_LIBRARY_CXXFLAGS
ARG QUARTZ_TOOL_CXXFLAGS
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake patch curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY compilers/quartz-compiler/build-requirements.txt /build/
RUN pip install --no-cache-dir --require-hashes -r /build/build-requirements.txt
WORKDIR /build
RUN curl -sSL -o quartz.tar.gz "https://github.com/quantum-compiler/quartz/archive/refs/tags/v${QUARTZ_VERSION}.tar.gz" \
    && echo "${QUARTZ_SHA256}  quartz.tar.gz" | sha256sum -c - \
    && tar xzf quartz.tar.gz && mv "quartz-${QUARTZ_VERSION}" quartz
COPY compilers/quartz-compiler/shift10-normalise.patch compilers/quartz-compiler/gen_nam_ecc.cpp compilers/quartz-compiler/quartz_greedy.cpp /build/
RUN cd quartz && patch -p1 < ../shift10-normalise.patch \
    && mkdir build && cd build \
    && cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="${QUARTZ_LIBRARY_CXXFLAGS}" \
    && make -j"$(nproc)" quartz_runtime
RUN for tool in gen_nam_ecc:gen-nam-ecc quartz_greedy:quartz-greedy; do \
        g++ ${QUARTZ_TOOL_CXXFLAGS} -I/build/quartz/src -I/build/quartz/src/quartz $(python -m pybind11 --includes) \
            "${tool%%:*}.cpp" -o "${tool##*:}" -Lquartz/build -lquartz_runtime $(python3-config --ldflags --embed) \
            -Wl,-rpath,/usr/local/lib/quartz || exit 1; \
    done
RUN mkdir -p /usr/local/lib/quartz && cp quartz/build/libquartz_runtime.so /usr/local/lib/quartz/ \
    && mkdir ecc && ./gen-nam-ecc "${ECC_MAX_GATES}" /build/ecc/Nam_ > ecc/generation.log 2>&1 \
    && echo "${ECC_SHA256}  ecc/Nam_complete_ECC_set.json" | sha256sum -c -

FROM python:3.13-slim@sha256:aaf08c5490d52cd92bc27142a5215b1e47355a5eaf9adfad2a0fbc022d0b5490

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT=20261020T213255Z
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${DEBIAN_SNAPSHOT}\$" /etc/apt/sources.list.d/debian.sources)" = 2

ARG QUARTZ_VERSION
ARG QUARTZ_SHA256
ARG ECC_MAX_GATES
ARG ECC_SHA256
ARG QUARTZ_LIBRARY_CXXFLAGS
ARG QUARTZ_TOOL_CXXFLAGS
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN useradd -m appuser
WORKDIR /home/appuser/app

COPY --from=quartz-build /usr/local/lib/quartz /usr/local/lib/quartz
# libquartz_runtime resolves its source directory (kQuartzRootPath) when it loads.
COPY --from=quartz-build /build/quartz/src/quartz /build/quartz/src/quartz
COPY --from=quartz-build /build/quartz-greedy /usr/local/bin/quartz-greedy
COPY --from=quartz-build /build/ecc/Nam_complete_ECC_set.json /usr/local/share/quartz/Nam_complete_ECC_set.json
COPY compilers/quartz-compiler/requirements.txt .
COPY compilers/quartz-compiler/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY shared /tmp/shared-src
# pip is not used at run time; uninstalling it removes the packages it vendors.
RUN pip install --no-cache-dir --no-deps --no-build-isolation --no-index /tmp/shared-src && \
    rm -rf /tmp/shared-src && \
    python -m pip uninstall --yes pip

COPY compilers/quartz-compiler/Dockerfile compilers/quartz-compiler/requirements.lock compilers/quartz-compiler/shift10-normalise.patch compilers/quartz-compiler/gen_nam_ecc.cpp compilers/quartz-compiler/quartz_greedy.cpp compilers/quartz-compiler/build-requirements.txt /usr/local/share/qrosetta-build/
COPY --from=quartz-build /build/ecc/Nam_complete_ECC_set.json /usr/local/share/qrosetta-build/
COPY compilers/quartz-compiler/main.py .

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
ENV QUARTZ_VERSION=${QUARTZ_VERSION} \
    QUARTZ_SHA256=${QUARTZ_SHA256} \
    QUARTZ_BUILD_FLAGS="library: CMake Release, CXXFLAGS ${QUARTZ_LIBRARY_CXXFLAGS}; tools: g++ ${QUARTZ_TOOL_CXXFLAGS}" \
    QUARTZ_ECC_SET=/usr/local/share/quartz/Nam_complete_ECC_set.json \
    QUARTZ_ECC_MAX_GATES=${ECC_MAX_GATES} \
    QUARTZ_ECC_SHA256=${ECC_SHA256}
USER appuser

CMD ["sh", "-c", "exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
