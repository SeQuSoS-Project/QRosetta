FROM python:3.10-slim

# Create a non-root user
RUN useradd -m appuser
WORKDIR /home/appuser/app

# Copy requirements and install dependencies
COPY pytket-cirq-runner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library and install it
COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

# Copy application code
COPY pytket-cirq-runner/main.py .

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser /home/appuser/app
USER appuser

CMD ["gunicorn", "main:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-"]
