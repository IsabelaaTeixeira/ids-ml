# Imagem da demonstração: o pacote nids com o grupo de dependências demo, usada pelo replay
# (nids replay) e pelo painel (Streamlit). Os dois dividem o banco em /demo (docker-compose.yml).

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Como na imagem da API: sem o NCCL do XGBoost, e dependências antes do código
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --group demo --no-install-project \
    --no-install-package nvidia-nccl-cu13
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-default-groups --group demo --no-editable \
    --no-install-package nvidia-nccl-cu13

FROM python:3.12-slim
# A libgomp é do XGBoost, que o comando nids importa. /demo nasce do usuário nids para o volume
# do banco herdar o dono.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nids \
    && mkdir /demo && chown nids /demo
COPY --from=build /app/.venv /app/.venv
COPY dashboard /app/dashboard
COPY .streamlit /app/.streamlit
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" NIDS_DEMO_DB=/demo/replay.db
USER nids
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
