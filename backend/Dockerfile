FROM python:3.11-slim

WORKDIR /app

# Install initial requirements for the scaffolding
RUN pip install --no-cache-dir fastapi uvicorn

# Note: The code will be mounted from the host for hot-reloading in docker-compose,
# but we safely copy the contents anyway.
COPY . .

# Run uvicorn with hot-reload enabled
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
