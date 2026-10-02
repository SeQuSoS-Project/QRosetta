ARG QUARTZ_VERSION=0.3.2
ARG QUARTZ_SHA256=4563a45382ae6da3ed7528b73bee4472fa147c3f17133b9282ab1d6fb27e2dcc
ARG ECC_MAX_GATES=3
ARG ECC_SHA256=e68e9c41229a675e0e0b5dcb97716cc0c0e6ffe15fa2ade13aed6b01a1140d05

FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634 AS quartz-build

ARG QUARTZ_VERSION
ARG QUARTZ_SHA256
ARG ECC_MAX_GATES
ARG ECC_SHA256
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake patch curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY compilers/quartz-compiler/build-requirements.txt /build/
RUN pip install --no-cache-dir -r /build/build-requirements.txt
WORKDIR /build
RUN curl -sSL -o quartz.tar.gz "https://github.com/quantum-compiler/quartz/archive/refs/tags/v${QUARTZ_VERSION}.tar.gz" \
    && echo "${QUARTZ_SHA256}  quartz.tar.gz" | sha256sum -c - \
    && tar xzf quartz.tar.gz && mv "quartz-${QUARTZ_VERSION}" quartz
COPY compilers/quartz-compiler/shift10-normalise.patch compilers/quartz-compiler/gen_nam_ecc.cpp compilers/quartz-compiler/quartz_greedy.cpp /build/
RUN cd quartz && patch -p1 < ../shift10-normalise.patch \
    && mkdir build && cd build \
    && cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-include algorithm" \
    && make -j"$(nproc)" quartz_runtime
RUN for tool in gen_nam_ecc:gen-nam-ecc quartz_greedy:quartz-greedy; do \
        g++ -std=c++17 -O2 -fopenmp -DUSE_RATIONAL -I/build/quartz/src -I/build/quartz/src/quartz $(python -m pybind11 --includes) \
            "${tool%%:*}.cpp" -o "${tool##*:}" -Lquartz/build -lquartz_runtime $(python3-config --ldflags --embed) \
            -Wl,-rpath,/usr/local/lib/quartz || exit 1; \
    done
RUN mkdir -p /usr/local/lib/quartz && cp quartz/build/libquartz_runtime.so /usr/local/lib/quartz/ \
    && mkdir ecc && ./gen-nam-ecc "${ECC_MAX_GATES}" /build/ecc/Nam_ > ecc/generation.log 2>&1 \
    && echo "${ECC_SHA256}  ecc/Nam_complete_ECC_set.json" | sha256sum -c -

FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634

ARG QUARTZ_VERSION
ARG QUARTZ_SHA256
ARG ECC_MAX_GATES
ARG ECC_SHA256
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
RUN pip install --no-cache-dir -r requirements.lock

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY compilers/quartz-compiler/Dockerfile compilers/quartz-compiler/requirements.lock compilers/quartz-compiler/shift10-normalise.patch compilers/quartz-compiler/gen_nam_ecc.cpp compilers/quartz-compiler/quartz_greedy.cpp /usr/local/share/qrosetta-build/
COPY --from=quartz-build /build/ecc/Nam_complete_ECC_set.json /usr/local/share/qrosetta-build/
COPY compilers/quartz-compiler/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ENV PYTHONHASHSEED=0
ENV QUARTZ_VERSION=${QUARTZ_VERSION} \
    QUARTZ_SHA256=${QUARTZ_SHA256} \
    QUARTZ_ECC_SET=/usr/local/share/quartz/Nam_complete_ECC_set.json \
    QUARTZ_ECC_MAX_GATES=${ECC_MAX_GATES} \
    QUARTZ_ECC_SHA256=${ECC_SHA256}
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
