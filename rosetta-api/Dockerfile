FROM python:3.10-slim

# Create a non-root user
RUN useradd -m appuser
WORKDIR /home/appuser/app

# Copy requirements using the correct path relative to project root
COPY rosetta-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library and install it (Crucial step for the Logger)
COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

# Copy application code
COPY rosetta-api/ .

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser /home/appuser/app
USER appuser

# Start Gunicorn with 4 workers for the API
CMD ["gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "60", "--access-logfile", "-"]