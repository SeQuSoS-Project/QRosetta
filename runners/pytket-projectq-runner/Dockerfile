FROM python:3.10-slim@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d

# --- FIX 1: Install System Dependencies ---
# 'libgomp1' is REQUIRED for ProjectQ runtime (avoids the crash).
# 'build-essential', 'g++', 'git' are required for compiling ProjectQ.
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m appuser
WORKDIR /home/appuser/app

# Copy requirements
COPY runners/pytket-projectq-runner/requirements.txt .
COPY runners/pytket-projectq-runner/requirements.lock .
ENV PIP_DEFAULT_TIMEOUT=1000

# --- FIX 2: Pre-install Build Tools ---
# 'setuptools<70' prevents the 'dry_run' attribute error.
# 'setuptools_scm' prevents the version '0.0.0' error.
RUN pip install --no-cache-dir "setuptools==69.5.1" "setuptools-scm==10.2.0" "wheel==0.45.1" "pybind11==3.0.4"

# --- FIX 3: Disable Build Isolation ---
# Forces pip to use the compatible tools we just installed above.
RUN pip install --no-build-isolation --no-cache-dir -r requirements.lock

# Copy shared library and install it
COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src && rm -rf /tmp/shared-src

# Copy application code
COPY runners/pytket-projectq-runner/main.py .

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u,o=rX /home/appuser
ENV HOME=/home/appuser
COPY runners/pytket-projectq-runner/Dockerfile runners/pytket-projectq-runner/requirements.lock /usr/local/share/qrosetta-build/
ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}
ARG QROSETTA_IMAGE_SOURCE=unknown
ARG QROSETTA_RELEASE=
RUN mkdir -p /usr/local/share/qrosetta-image \
    && printf 'source=%s\nrelease=%s\ngit_sha=%s\n' "$QROSETTA_IMAGE_SOURCE" "$QROSETTA_RELEASE" "$QROSETTA_GIT_SHA" \
       > /usr/local/share/qrosetta-image/identity
USER appuser

# Original CMD (Preserves consistency with your other runners)
CMD ["sh", "-c", "exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]