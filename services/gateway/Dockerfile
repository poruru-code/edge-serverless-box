FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependencies
COPY pyproject.toml /app/

# Install dependencies (Cache layer)
RUN uv pip install --system --break-system-packages "fastapi" "uvicorn[standard]" "requests" "httpx" "pyjwt" "respx" "pyyaml" "pydantic" "pydantic-settings" "python-json-logger" "python-dotenv"

# Copy services code
COPY services/gateway /app/services/gateway
# Copy Config
COPY config /app/config

EXPOSE 443

CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "443", "--ssl-keyfile", "/app/config/ssl/server.key", "--ssl-certfile", "/app/config/ssl/server.crt"]
