"""Fonte única dos nomes de colunas, rótulos e famílias do CIC-IDS2017.

Os CSVs originais têm nomes com espaços, maiúsculas e barras. `normalize_name`
converte tudo para snake_case, e o resto do código usa só os nomes definidos aqui.
"""

import re
from typing import Literal, get_args

Day = Literal["monday", "tuesday", "wednesday", "thursday", "friday"]
DAYS: list[str] = list(get_args(Day))

# Data de captura de cada dia. O Timestamp dos CSVs usa dia/mês/ano.
DAY_DATES = {
    "monday": "2017-07-03",
    "tuesday": "2017-07-04",
    "wednesday": "2017-07-05",
    "thursday": "2017-07-06",
    "friday": "2017-07-07",
}

# Colunas dos CSVs (versão GeneratedLabelledFlows) na ordem original, já normalizadas.
# "Fwd Header Length" aparece duas vezes no original; o pandas renomeia a segunda com ".1".
RAW_COLUMNS = [
    "flow_id",
    "source_ip",
    "source_port",
    "destination_ip",
    "destination_port",
    "protocol",
    "timestamp",
    "flow_duration",
    "total_fwd_packets",
    "total_backward_packets",
    "total_length_of_fwd_packets",
    "total_length_of_bwd_packets",
    "fwd_packet_length_max",
    "fwd_packet_length_min",
    "fwd_packet_length_mean",
    "fwd_packet_length_std",
    "bwd_packet_length_max",
    "bwd_packet_length_min",
    "bwd_packet_length_mean",
    "bwd_packet_length_std",
    "flow_bytes_s",
    "flow_packets_s",
    "flow_iat_mean",
    "flow_iat_std",
    "flow_iat_max",
    "flow_iat_min",
    "fwd_iat_total",
    "fwd_iat_mean",
    "fwd_iat_std",
    "fwd_iat_max",
    "fwd_iat_min",
    "bwd_iat_total",
    "bwd_iat_mean",
    "bwd_iat_std",
    "bwd_iat_max",
    "bwd_iat_min",
    "fwd_psh_flags",
    "bwd_psh_flags",
    "fwd_urg_flags",
    "bwd_urg_flags",
    "fwd_header_length",
    "bwd_header_length",
    "fwd_packets_s",
    "bwd_packets_s",
    "min_packet_length",
    "max_packet_length",
    "packet_length_mean",
    "packet_length_std",
    "packet_length_variance",
    "fin_flag_count",
    "syn_flag_count",
    "rst_flag_count",
    "psh_flag_count",
    "ack_flag_count",
    "urg_flag_count",
    "cwe_flag_count",
    "ece_flag_count",
    "down_up_ratio",
    "average_packet_size",
    "avg_fwd_segment_size",
    "avg_bwd_segment_size",
    "fwd_header_length_1",
    "fwd_avg_bytes_bulk",
    "fwd_avg_packets_bulk",
    "fwd_avg_bulk_rate",
    "bwd_avg_bytes_bulk",
    "bwd_avg_packets_bulk",
    "bwd_avg_bulk_rate",
    "subflow_fwd_packets",
    "subflow_fwd_bytes",
    "subflow_bwd_packets",
    "subflow_bwd_bytes",
    "init_win_bytes_forward",
    "init_win_bytes_backward",
    "act_data_pkt_fwd",
    "min_seg_size_forward",
    "active_mean",
    "active_std",
    "active_max",
    "active_min",
    "idle_mean",
    "idle_std",
    "idle_max",
    "idle_min",
    "label",
]

ROW_ID = "row_id"
DAY = "day"
TIMESTAMP = "timestamp"
LABEL = "label"
FAMILY = "family"

# Descrevem o fluxo, mas nunca entram no modelo: os ataques partem de poucos IPs fixos,
# então o modelo aprenderia o endereço em vez do ataque (seção 5.4 da arquitetura).
METADATA = [ROW_ID, DAY, TIMESTAMP, "source_ip", "source_port", "destination_ip"]

# Removidas na limpeza. O motivo vai para o relatório de qualidade.
DROPPED = {
    "flow_id": "redundante: junta IPs, portas e protocolo",
    "fwd_header_length_1": "cópia de fwd_header_length",
    "bwd_psh_flags": "constante",
    "bwd_urg_flags": "constante",
    "fwd_avg_bytes_bulk": "constante",
    "fwd_avg_packets_bulk": "constante",
    "fwd_avg_bulk_rate": "constante",
    "bwd_avg_bytes_bulk": "constante",
    "bwd_avg_packets_bulk": "constante",
    "bwd_avg_bulk_rate": "constante",
}

FEATURES = [c for c in RAW_COLUMNS if c not in DROPPED and c not in METADATA and c != LABEL]

# Colunas do dataset limpo (data/interim/flows.parquet), nesta ordem.
CLEAN_COLUMNS = [*METADATA, *FEATURES, LABEL, FAMILY]

BENIGN = "BENIGN"

# Rótulo normalizado -> (rótulo canônico, família de ataque), na ordem dos dias de captura.
# A chave normalizada absorve o problema de encoding em "Web Attack – Brute Force".
LABELS = {
    "benign": (BENIGN, BENIGN),
    "ftp patator": ("FTP-Patator", "BruteForce"),
    "ssh patator": ("SSH-Patator", "BruteForce"),
    "dos slowloris": ("DoS slowloris", "DoS"),
    "dos slowhttptest": ("DoS Slowhttptest", "DoS"),
    "dos hulk": ("DoS Hulk", "DoS"),
    "dos goldeneye": ("DoS GoldenEye", "DoS"),
    "heartbleed": ("Heartbleed", "Heartbleed"),
    "web attack brute force": ("Web Attack - Brute Force", "WebAttack"),
    "web attack xss": ("Web Attack - XSS", "WebAttack"),
    "web attack sql injection": ("Web Attack - Sql Injection", "WebAttack"),
    "infiltration": ("Infiltration", "Infiltration"),
    "bot": ("Bot", "Bot"),
    "portscan": ("PortScan", "PortScan"),
    "ddos": ("DDoS", "DDoS"),
}
LABEL_NAMES = [canonical for canonical, _ in LABELS.values()]
FAMILY_OF = dict(LABELS.values())
FAMILIES = list(dict.fromkeys(FAMILY_OF.values()))


def normalize_name(name: str) -> str:
    """' Flow Bytes/s' -> 'flow_bytes_s'."""
    return re.sub(r"[^0-9a-z]+", "_", name.lower()).strip("_")


def normalize_label(label: str) -> str:
    """'Web Attack – Brute Force' -> 'web attack brute force'."""
    return re.sub(r"[^0-9a-z]+", " ", label.lower()).strip()
