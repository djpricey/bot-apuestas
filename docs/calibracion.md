# Calibración (generado por src/calibracion.py)

Picks liquidados con probabilidad: 33. Con menos de ~200 nada es concluyente; con menos de 20 en un grupo, solo es una pista.

| Grupo | n | Prometido | Real | Diferencia | Stakes | Balance | ROI |
|---|---|---|---|---|---|---|---|
| TOTAL | 33 | 61% | 58% | -4% | 23.5 | +1.07 | +5% |
| cuota 1.25-1.60 | 11 | 74% | 55% | -20% | 9.0 | -1.86 | -21% |
| cuota 1.60-2.20 | 16 | 63% | 62% | -0% | 11.0 | -0.13 | -1% |
| cuota 2.20+ | 6 | 34% | 50% | +16% | 3.5 | +3.06 | +88% |
| mercado: ambos marcan | 4 | 59% | 50% | -9% | 3.5 | -0.29 | -8% |
| mercado: córners menos | 5 | 69% | 20% | -49% | 4.5 | -3.64 | -81% |
| mercado: córners más | 8 | 69% | 62% | -6% | 4.5 | -0.38 | -8% |
| mercado: goles menos | 6 | 53% | 67% | +13% | 5.5 | +2.13 | +39% |
| mercado: resultado | 2 | 46% | 100% | +54% | 1.5 | +2.65 | +177% |
| mercado: tarjetas menos | 4 | 60% | 75% | +16% | 2.0 | +0.85 | +42% |
| mercado: tarjetas más | 4 | 60% | 50% | -10% | 2.0 | -0.25 | -12% |

## Cómo usarlo
- Si un grupo con n ≥ 20 sale con 'Real' más de 8 puntos por debajo de 'Prometido', recorta esas probabilidades (o deja de recomendar ese mercado) y anótalo en notas_analista.md.
- Si sale por encima con n ≥ 20, el modelo es conservador ahí: puede pesar más que el mercado (65/35).
- Con n < 20, no cambies nada por esta tabla; úsala solo como alerta.
