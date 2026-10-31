"""API HTTP do IDS: recebe fluxos e devolve um veredito por fluxo (seção 9 da arquitetura).

Rode com `uvicorn nids.serving.api:create_app --factory`. Os modelos são lidos uma vez, na
subida; se algo estiver errado com eles, a API não sobe.
"""

from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, create_model
from pydantic_settings import BaseSettings, SettingsConfigDict

from nids.schema import FEATURES
from nids.serving.predictor import load_predictor


class Settings(BaseSettings):
    """Vêm das variáveis de ambiente NIDS_MODEL_DIR, NIDS_CLASSIFIER e assim por diante."""

    model_config = SettingsConfigDict(env_prefix="NIDS_")

    model_dir: Path = Path("models")
    classifier: str = "xgb_temporal"
    detector: str = "ae_unseen"
    max_batch: int = Field(default=1000, gt=0)


# Um fluxo como sai do pipeline de dados: os atributos de schema.FEATURES, finitos. Campos a
# mais são recusados, para que um IP ou horário nunca chegue ao modelo por engano.
Flow = create_model(
    "Flow",
    __config__=ConfigDict(extra="forbid"),
    **{feature: (FiniteFloat, ...) for feature in FEATURES},
)


class Verdict(BaseModel):
    verdict: Literal["attack", "suspicious", "benign"]
    family: str | None
    attack_probability: float
    anomaly_score: float


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

    app = FastAPI(title="IDS com Machine Learning")

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError) -> JSONResponse:
        # O handler padrão devolve a entrada no erro, e NaN ou infinito não cabem em JSON
        errors = [{k: v for k, v in error.items() if k != "input"} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/model")
    def model() -> dict[str, dict]:
        """Metadados dos modelos carregados: limiares, atributos, classes e versões."""
        return {
            "classifier": predictor.classifier.metadata,
            "detector": predictor.detector.metadata,
        }

    @app.post("/predict")
    def predict(request: PredictRequest) -> Prediction:
        frame = pd.DataFrame([flow.model_dump() for flow in request.flows])
        return Prediction(models=models, results=predictor.predict(frame))

    return app
