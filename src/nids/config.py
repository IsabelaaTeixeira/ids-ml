"""Leitura e validação dos arquivos de configuração (YAML)."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator, model_validator

from nids.schema import FEATURES, Day


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Paths(_Config):
    raw: Path
    interim: Path
    processed: Path
    reports: Path
    checksums: Path
    models: Path = Path("models")


class TimestampConfig(_Config):
    first_capture_hour: int = Field(ge=1, le=12)


class UnseenSplit(_Config):
    train_days: list[Day] = Field(min_length=1)
    test_days: list[Day] = Field(min_length=1)
    val_fraction: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def _days_are_disjoint(self) -> "UnseenSplit":
        overlap = set(self.train_days) & set(self.test_days)
        if overlap:
            raise ValueError(f"dias no treino e no teste ao mesmo tempo: {sorted(overlap)}")
        return self


class SplitConfig(_Config):
    seed: int
    fractions: tuple[PositiveFloat, PositiveFloat, PositiveFloat]
    unseen: UnseenSplit

    @field_validator("fractions")
    @classmethod
    def _sum_to_one(cls, fractions: tuple[float, float, float]) -> tuple[float, float, float]:
        if abs(sum(fractions) - 1) > 1e-9:
            raise ValueError(f"as frações precisam somar 1 (somam {sum(fractions)})")
        return fractions


class DataConfig(_Config):
    paths: Paths
    timestamp: TimestampConfig
    split: SplitConfig


class ExperimentConfig(_Config):
    """Um treino (configs/experiments/*.yaml): classificador ou detector de anomalia."""

    name: str
    protocol: Literal["random", "temporal", "unseen"]
    model: Literal["xgboost", "random_forest", "isolation_forest", "autoencoder"]
    params: dict[str, Any] = Field(default_factory=dict)
    use_destination_port: bool = False  # ADR 0004
    exclude_features: list[str] = Field(default_factory=list)
    # FPR escolhida nos fluxos normais da validação para fixar o limiar de alarme
    target_fpr: float = Field(default=0.01, gt=0, lt=1)
    seed: int = 42

    @field_validator("exclude_features")
    @classmethod
    def _known_features(cls, names: list[str]) -> list[str]:
        unknown = sorted(set(names) - set(FEATURES))
        if unknown:
            raise ValueError(f"atributos desconhecidos: {unknown}")
        return names


def load_data_config(path: Path) -> DataConfig:
    with path.open(encoding="utf-8") as f:
        return DataConfig.model_validate(yaml.safe_load(f))


def load_experiment_config(path: Path) -> ExperimentConfig:
    with path.open(encoding="utf-8") as f:
        return ExperimentConfig.model_validate(yaml.safe_load(f))
