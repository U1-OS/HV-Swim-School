# Production API + static site (single origin). Build from repository root:
#   docker build -f deploy/Dockerfile -t hv-swim .
#
# Secrets and .env stay on the host or orchestrator — never COPY them into the image.

FROM python:3.12-slim-bookworm

WORKDIR /app

RUN groupadd --system --gid 1000 hvswim \
  && useradd --system --uid 1000 --gid hvswim --home-dir /app hvswim

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/deploy/entrypoint.sh \
  && chown -R hvswim:hvswim /app

USER hvswim

ENV HV_LOAD_DOTENV=false \
    PYTHONUNBUFFERED=1 \
    HV_UVICORN_HOST=0.0.0.0 \
    HV_UVICORN_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
