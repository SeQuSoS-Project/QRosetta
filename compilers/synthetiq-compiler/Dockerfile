ARG SYNTHETIQ_COMMIT=59a0cc6942c9561033a762ced2c35ceab9b876c3
ARG SYNTHETIQ_SHA256=90d553544d13bca950ab47726b8543fffaaea2554e5edad6cd10b6090c7156d6
ARG SYNTHETIQ_CXXFLAGS="-std=c++17 -fopenmp -O2 -DEIGEN_NO_DEBUG"

FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634 AS synthetiq-build

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

FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634

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
RUN pip install --no-cache-dir -r requirements.lock

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY compilers/synthetiq-compiler/Dockerfile compilers/synthetiq-compiler/requirements.lock compilers/synthetiq-compiler/max-runs.patch /usr/local/share/qrosetta-build/
COPY compilers/synthetiq-compiler/main.py .

RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ENV PYTHONHASHSEED=0
ENV SYNTHETIQ_COMMIT=${SYNTHETIQ_COMMIT} \
    SYNTHETIQ_SHA256=${SYNTHETIQ_SHA256} \
    SYNTHETIQ_CXXFLAGS=${SYNTHETIQ_CXXFLAGS} \
    OMP_NUM_THREADS=1
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
