FROM python:3.14-slim AS builder

WORKDIR /app

# Install build deps
RUN pip install --no-cache-dir hatchling

# Copy project metadata first for layer caching
COPY pyproject.toml README.md ./
COPY src/ src/

# Build wheel
RUN pip wheel --no-deps --wheel-dir /wheels .

# ---------- runtime ----------
FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /wheels /wheels

# Install package + harmonic extras
RUN pip install --no-cache-dir /wheels/*.whl && \
    pip install --no-cache-dir "utide>=0.3.0" "scipy>=1.10.0" && \
    rm -rf /wheels

# Non-root user
RUN useradd -m tides
USER tides

EXPOSE 8003

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["chuk-mcp-tides"]
CMD ["http", "--host", "0.0.0.0", "--port", "8003"]
