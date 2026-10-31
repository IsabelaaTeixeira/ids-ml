# Imagem da API: o pacote nids com o grupo de dependências api, sem ferramentas de
# desenvolvimento nem notebooks. Os modelos entram por volume em /models (docker-compose.yml).

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# O NCCL serve para treinar em várias GPUs; o XGBoost só o carrega se for usado, e ele
# ocupa centenas de MB. Dependências antes do código: mudar o código não reinstala tudo.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --group api --no-install-project \
    --no-install-package nvidia-nccl-cu13
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-default-groups --group api --no-editable \
    --no-install-package nvidia-nccl-cu13

FROM python:3.12-slim
# O XGBoost precisa da libgomp, que a imagem slim não traz
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nids
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" NIDS_MODEL_DIR=/models
USER nids
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
CMD ["uvicorn", "nids.serving.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
