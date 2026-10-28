"""Invariantes do dataset limpo. Se alguma falhar, o pipeline para em vez de seguir com
dados quebrados."""

import numpy as np
import pandas as pd

from nids import schema


class DataValidationError(ValueError):
    """O dataset limpo violou alguma invariante."""


def validate_clean(df: pd.DataFrame) -> None:
    if list(df.columns) != schema.CLEAN_COLUMNS:
        raise DataValidationError("colunas diferentes de schema.CLEAN_COLUMNS")

    problems = []
    not_float32 = [c for c in schema.FEATURES if df[c].dtype != np.float32]
    if not_float32:
        problems.append(f"features que não são float32: {not_float32}")
    not_finite = [c for c in schema.FEATURES if not np.isfinite(df[c].to_numpy()).all()]
    if not_finite:
        problems.append(f"features com NaN ou infinito: {not_finite}")
    # O -1 das janelas TCP significa "não observada" (ADR 0006)
    negative = [c for c in schema.FEATURES if df[c].min() < (-1 if "init_win" in c else 0)]
    if negative:
        problems.append(f"valores negativos: {negative}")
    if df[schema.TIMESTAMP].isna().any():
        problems.append("timestamps faltando")
    if df[schema.LABEL].isna().any():
        problems.append("rótulos faltando ou fora de schema.LABELS")
    families = df[schema.LABEL].astype(str).map(schema.FAMILY_OF)
    if (df[schema.FAMILY].astype(str) != families).any():
        problems.append("família não corresponde ao rótulo")
    if df.duplicated(subset=[*schema.FEATURES, schema.LABEL]).any():
        problems.append("linhas duplicadas")

    if problems:
        raise DataValidationError("; ".join(problems))
