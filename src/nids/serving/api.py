"""API HTTP do IDS: recebe fluxos e devolve um veredito por fluxo (seção 9 da arquitetura).

Rode com `uvicorn nids.serving.api:create_app --factory`. Os modelos são lidos uma vez, na
subida; se algo estiver errado com eles, a API não sobe.
"""

import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, SecretStr, create_model
from pydantic_settings import BaseSettings, SettingsConfigDict

from nids.schema import FEATURES
from nids.serving.predictor import load_predictor

API_KEY = APIKeyHeader(name="X-API-Key", auto_error=False)


class Settings(BaseSettings):
    """Vêm das variáveis de ambiente NIDS_MODEL_DIR, NIDS_CLASSIFIER e assim por diante."""

    model_config = SettingsConfigDict(env_prefix="NIDS_")

    model_dir: Path = Path("models")
    classifier: str = "xgb_temporal"
    detector: str = "ae_unseen"
    max_batch: int = Field(default=1000, gt=0)
    # Desligados por padrão, para a demonstração local; ligue os dois antes de expor a API
    api_key: SecretStr | None = None
    rate_limit: int | None = Field(default=None, gt=0)  # requisições por minuto, por cliente


# Um fluxo como sai do pipeline de dados: os atributos de schema.FEATURES, finitos. Campos a
# mais são recusados, para que um IP ou horário nunca chegue ao modelo por engano.
Flow = create_model(
    "Flow",
    __config__=ConfigDict(extra="forbid"),
    **{feature: (FiniteFloat, ...) for feature in FEATURES},
)


class Contribution(BaseModel):
    """Um atributo e o quanto pesou no alerta, na escala do modelo que o disparou."""

    feature: str
    weight: float


class Verdict(BaseModel):
    verdict: Literal["attack", "suspicious", "benign"]
    family: str | None
    attack_probability: float
    anomaly_score: float
    # Os atributos que mais pesaram, do maior para o menor; vazio nos fluxos normais
    explanation: list[Contribution] = []


class Prediction(BaseModel):
    models: dict[str, str]
    results: list[Verdict]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    predictor = load_predictor(settings.model_dir, settings.classifier, settings.detector)
    models = {
        "classifier": predictor.classifier.metadata["name"],
        "detector": predictor.detector.metadata["name"],
    }

    class PredictRequest(BaseModel):
        flows: list[Flow] = Field(min_length=1, max_length=settings.max_batch)

    def require_key(key: str | None = Security(API_KEY)) -> None:
        expected = settings.api_key
        # compare_digest leva o mesmo tempo com a chave certa ou errada
        if expected and not (key and secrets.compare_digest(key, expected.get_secret_value())):
            raise HTTPException(401, "chave de acesso ausente ou errada (cabeçalho X-API-Key)")

    recent: dict[str, deque[float]] = defaultdict(deque)

    def limit_rate(request: Request) -> None:
        # Janela deslizante de um minuto, em memória: vale para um processo só
        if settings.rate_limit is None:
            return
        now = time.monotonic()
        calls = recent[request.client.host if request.client else "?"]
        while calls and now - calls[0] >= 60:
            calls.popleft()
        if len(calls) >= settings.rate_limit:
            retry = int(60 - (now - calls[0])) + 1
            raise HTTPException(
                429, "limite de requisições por minuto", {"Retry-After": str(retry)}
            )
        calls.append(now)

    protected = [Depends(require_key), Depends(limit_rate)]
    app = FastAPI(title="IDS com Machine Learning")

    # Um registro por app: criar a API de novo (como nos testes) não duplica as métricas
    registry = CollectorRegistry()
    verdicts = Counter("nids_verdicts", "Vereditos dados, por tipo", ["verdict"], registry=registry)
    for verdict in Verdict.model_fields["verdict"].annotation.__args__:
        verdicts.labels(verdict)
    latency = Histogram("nids_predict_seconds", "Tempo de resposta do /predict", registry=registry)

    @app.get("/metrics")
    def metrics() -> Response:
        """Formato do Prometheus; como o /health, fica aberto, para uso dentro da rede."""
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError) -> JSONResponse:
        # O handler padrão devolve a entrada no erro, e NaN ou infinito não cabem em JSON
        errors = [{k: v for k, v in error.items() if k != "input"} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/model", dependencies=protected)
    def model() -> dict[str, dict]:
        """Metadados dos modelos carregados: limiares, atributos, classes e versões."""
        return {
            "classifier": predictor.classifier.metadata,
            "detector": predictor.detector.metadata,
        }

    @app.post("/predict", dependencies=protected)
    def predict(request: PredictRequest, explain: bool = True) -> Prediction:
        """Com `explain=false`, os alertas vêm sem explicação: a resposta fica até 20 vezes mais
        rápida num lote cheio de ataques (ADR 0013)."""
        with latency.time():
            frame = pd.DataFrame([flow.model_dump() for flow in request.flows])
            results = predictor.predict(frame, explain=explain)
        for result in results:
            verdicts.labels(result["verdict"]).inc()
        return Prediction(models=models, results=results)

    return app
