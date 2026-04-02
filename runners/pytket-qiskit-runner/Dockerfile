FROM python:3.10-slim

# Create a non-root user
RUN useradd -m appuser
WORKDIR /home/appuser/app

# Copy requirements and install dependencies
COPY runners/pytket-qiskit-runner/requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library and install it
COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

# Copy application code
COPY runners/pytket-qiskit-runner/main.py .

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser /home/appuser/app && \
    chgrp -R 0 /home/appuser && \
    chmod -R g=u /home/appuser
ENV HOME=/home/appuser
USER appuser

CMD ["sh", "-c", "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 330 --access-logfile -"]
