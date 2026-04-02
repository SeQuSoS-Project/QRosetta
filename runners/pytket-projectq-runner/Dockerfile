FROM python:3.10-slim

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
ENV PIP_DEFAULT_TIMEOUT=1000

# --- FIX 2: Pre-install Build Tools ---
# 'setuptools<70' prevents the 'dry_run' attribute error.
# 'setuptools_scm' prevents the version '0.0.0' error.
RUN pip install "setuptools<70" "setuptools_scm>=7" wheel pybind11

# --- FIX 3: Disable Build Isolation ---
# Forces pip to use the compatible tools we just installed above.
RUN pip install --no-build-isolation --no-cache-dir -r requirements.txt

# Copy shared library and install it
COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src && rm -rf /tmp/shared-src

# Copy application code
COPY runners/pytket-projectq-runner/main.py .

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ENV HOME=/home/appuser
USER appuser

# Original CMD (Preserves consistency with your other runners)
CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]