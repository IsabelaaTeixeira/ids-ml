"""Painel da demonstração (etapa 5): lê o banco do replay e mostra alertas, acertos e erros.

Rode `streamlit run dashboard/app.py` enquanto `nids replay` manda o teste do P2 para a API.
O banco vem de NIDS_DEMO_DB (padrão data/demo/replay.db).
"""

import os
import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from nids.demo.summary import VERDICTS, by_family, per_minute, recent_alerts, totals

DB = Path(os.environ.get("NIDS_DEMO_DB", "data/demo/replay.db"))

# Slots 1 a 3 da paleta categórica do projeto, nesta ordem: validados para qualquer par nos dois
# temas. No escuro, os mesmos matizes num passo próprio para o fundo escuro.
SERIES = ["Ataques reais", "Alertas de ataque", "Alertas suspeitos"]
COLORS = {"light": ["#2a78d6", "#eb6834", "#1baf7a"], "dark": ["#3987e5", "#d95926", "#199e70"]}
MUTED = "#898781"
DAYS = {"2017-07-06": "Quinta-feira, 6 de julho", "2017-07-07": "Sexta-feira, 7 de julho"}
VERDICT_NAMES = {"attack": "ataque", "suspicious": "suspeito"}


def number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def percent(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f} %".replace(".", ",")


def minute_chart(data: pd.DataFrame, colors: list[str]) -> alt.LayerChart:
    """Três séries de fluxos por minuto num só eixo, com régua e valores ao passar o mouse."""
    columns = {"true_attacks": SERIES[0], "attack": SERIES[1], "suspicious": SERIES[2]}
    wide = data.rename(columns=columns)[SERIES].reset_index()
    long = wide.melt("timestamp", var_name="série", value_name="fluxos")
    x = alt.X("timestamp:T", title=None, axis=alt.Axis(format="%H:%M"))
    color = alt.Color(
        "série:N",
        scale=alt.Scale(domain=SERIES, range=colors),
        legend=alt.Legend(orient="top", title=None),
    )
    # O Vega formata milhares com vírgula; o painel usa ponto, como no resto da página
    y = alt.Y(
        "fluxos:Q",
        title="fluxos por minuto",
        axis=alt.Axis(labelExpr="replace(format(datum.value, ','), regexp(',', 'g'), '.')"),
    )
    hover = alt.selection_point(nearest=True, on="pointerover", fields=["timestamp"], empty=False)
    lines = alt.Chart(long).mark_line(strokeWidth=2).encode(x=x, y=y, color=color)
    points = lines.mark_point(size=64, filled=True).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0))
    )
    for series in SERIES:
        wide[f"{series} (texto)"] = wide[series].map(number)
    tooltip = [alt.Tooltip("timestamp:T", title="minuto", format="%H:%M")]
    tooltip += [alt.Tooltip(f"{series} (texto):N", title=series) for series in SERIES]
    rule = (
        alt.Chart(wide)
        .mark_rule(color=MUTED)
        .encode(x=x, opacity=alt.condition(hover, alt.value(1), alt.value(0)), tooltip=tooltip)
        .add_params(hover)
    )
    return alt.layer(lines, points, rule).properties(height=260)


st.set_page_config(page_title="IDS · replay", layout="wide")
st.title("Replay do teste do P2")
st.caption(
    "Quinta e sexta-feira do CIC-IDS2017 passando pela API, minuto a minuto. O XGBoost do P2 e o "
    "autoencoder nunca viram esses ataques; o rótulo verdadeiro mostra os acertos e os erros."
)


@st.fragment(run_every="3s")
def dashboard() -> None:
    try:
        stats = totals(DB)
    except sqlite3.OperationalError:  # o replay ainda não criou o banco
        stats = None
    if not stats or not stats["flows"]:
        st.info("Aguardando o replay: rode `nids replay` ou `docker compose --profile demo up`.")
        return

    tiles = st.columns(4)
    tiles[0].metric("Fluxos analisados", number(stats["flows"]))
    tiles[1].metric(
        "Ataques detectados",
        percent(stats["recall"]),
        help=f"{number(stats['detected'])} de {number(stats['attacks'])} fluxos de ataque",
    )
    tiles[2].metric(
        "Alarmes falsos",
        number(stats["false_alarms"]),
        help=f"{percent(stats['fpr'])} dos fluxos normais",
    )
    tiles[3].metric("Alertas", number(stats["alerts"]))

    colors = COLORS["dark" if st.context.theme.type == "dark" else "light"]
    series = per_minute(DB)
    for day, data in series.groupby(series.index.date):
        st.subheader(DAYS.get(str(day), str(day)))
        st.altair_chart(minute_chart(data, colors), theme="streamlit")

    st.subheader("Acertos e erros por família")
    table = by_family(DB)
    count = st.column_config.NumberColumn(format="localized")
    st.dataframe(
        pd.DataFrame(
            {
                "Família verdadeira": table.index,
                "Fluxos": table[VERDICTS].sum(axis=1),
                "Ataque": table["attack"],
                "Suspeito": table["suspicious"],
                "Normal": table["benign"],
                "Com alerta": table["alert_rate"],
            }
        ),
        hide_index=True,
        column_config={
            "Fluxos": count,
            "Ataque": count,
            "Suspeito": count,
            "Normal": count,
            "Com alerta": st.column_config.NumberColumn(format="percent"),
        },
    )
    st.caption(
        "Nos ataques, “com alerta” é a revocação; no BENIGN, a taxa de alarmes falsos. Parte "
        "desses alarmes é tráfego de ataque rotulado como normal: respostas da vítima e a "
        "varredura feita pela máquina invadida na infiltração (notebook 03)."
    )

    st.subheader("Últimos alertas")
    alerts = recent_alerts(DB, n=15)
    st.dataframe(
        pd.DataFrame(
            {
                "Horário": alerts["timestamp"].dt.strftime("%d/%m %H:%M"),
                "Origem": alerts["source_ip"],
                "Destino": alerts["destination_ip"]
                + ":"
                + alerts["destination_port"].astype(int).astype(str),
                "Veredito": alerts["verdict"].map(VERDICT_NAMES),
                "Família prevista": alerts["predicted_family"].fillna("—"),
                "Família verdadeira": alerts["family"],
                "Resultado": alerts["correct"].map({True: "✓ acerto", False: "✗ alarme falso"}),
            }
        ),
        hide_index=True,
    )


dashboard()
