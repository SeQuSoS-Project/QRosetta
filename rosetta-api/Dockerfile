FROM python:3.10-slim

# Create a non-root user
RUN useradd -m appuser
WORKDIR /home/appuser/app

# Copy requirements and install dependencies
COPY rosetta-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY rosetta-api/ .

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser /home/appuser/app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
