FROM python:3.10-slim
WORKDIR /app

# Copy the runner-specific requirements
COPY pytket-quest-runner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire shared package source
COPY shared /tmp/shared-src

# Build and install the package
RUN pip install /tmp/shared-src

# Copy the runner-specific main file
COPY pytket-quest-runner/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]