FROM python:3.10-slim
WORKDIR /app

# Copy the API's requirements
COPY rosetta-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL the API's code (main.py, comparator.py, benchmarks/)
COPY rosetta-api/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]