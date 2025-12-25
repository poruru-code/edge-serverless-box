FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Create virtual environment
ENV VIRTUAL_ENV=/app/.venv
RUN uv venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy dependencies definition and source for package installation
COPY pyproject.toml README.md /app/
# tools package is required for "pip install ." as per pyproject.toml
COPY tools /app/tools

# 1. 外部依存関係のインストール
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install -r requirements.txt

# 2. アプリケーション自身をパッケージとしてインストール
# これにより importlib.metadata が "edge-serverless-box" を認識できるようになります
RUN uv pip install .

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# ソースコードのコピー
COPY services/common /app/services/common
COPY services/manager /app/services/manager
COPY config /app/config

CMD ["uvicorn", "services.manager.main:app", "--host", "0.0.0.0", "--port", "8081"]