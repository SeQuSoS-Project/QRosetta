FROM python:3.10-slim
WORKDIR /app

COPY pennylane-default-runner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src

COPY pennylane-default-runner/main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]