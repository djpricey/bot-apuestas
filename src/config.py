"""Ligas que sigue el modelo (fuente: football-data.co.uk)."""

BASE = "https://www.football-data.co.uk"

# Ligas principales: un CSV por temporada en /mmz4281/<temporada>/<código>.csv
LIGAS_PRINCIPALES = {
    "E0": "Premier League",
    "E1": "Championship",
    "SP1": "LaLiga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
    "N1": "Eredivisie",
    "P1": "Portugal",
    "B1": "Bélgica",
    "T1": "Turquía",
    "SC0": "Escocia",
}

# Ligas "extra": un solo CSV con toda la historia en /new/<código>.csv
LIGAS_EXTRA = {
    "ARG": "Argentina",
    "BRA": "Brasil",
    "MEX": "México",
    "USA": "MLS",
}

# Temporadas a descargar para las ligas principales (formato 2526 = 2025-26)
TEMPORADAS = ["2425", "2526", "2627"]

# Cuántos días de historia usar para ajustar el modelo
DIAS_HISTORIA = 730

# Candidatos de "olvido" (decaimiento por día). El modelo elige solo el que mejor predijo.
XI_CANDIDATOS = [0.0010, 0.0020, 0.0035]

# Ventaja mínima para marcar una apuesta como "valor"
EDGE_MIN = 0.05

# Correlación de marcadores bajos (Dixon-Coles)
RHO = -0.06
