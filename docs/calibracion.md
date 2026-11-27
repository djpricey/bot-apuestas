# Calibración (generado por src/calibracion.py)

Picks liquidados con probabilidad: 36. Con menos de ~200 nada es concluyente; con menos de 20 en un grupo, solo es una pista.

| Grupo | n | Prometido | Real | Diferencia | Stakes | Balance | ROI |
|---|---|---|---|---|---|---|---|
| TOTAL | 36 | 59% | 58% | -1% | 25.0 | +2.87 | +11% |
| cuota 1.25-1.60 | 11 | 74% | 55% | -20% | 9.0 | -1.86 | -21% |
| cuota 1.60-2.20 | 17 | 62% | 65% | +3% | 11.5 | +0.42 | +4% |
| cuota 2.20+ | 8 | 33% | 50% | +17% | 4.5 | +4.31 | +96% |
| mercado: ambos marcan | 4 | 59% | 50% | -9% | 3.5 | -0.29 | -8% |
| mercado: córners menos | 6 | 67% | 33% | -34% | 5.0 | -3.09 | -62% |
| mercado: córners más | 8 | 69% | 62% | -6% | 4.5 | -0.38 | -8% |
| mercado: goles menos | 6 | 53% | 67% | +13% | 5.5 | +2.13 | +39% |
| mercado: resultado | 4 | 37% | 75% | +38% | 2.5 | +3.90 | +156% |
| mercado: tarjetas menos | 4 | 60% | 75% | +16% | 2.0 | +0.85 | +42% |
| mercado: tarjetas más | 4 | 60% | 50% | -10% | 2.0 | -0.25 | -12% |

## Cómo usarlo
- Si un grupo con n ≥ 20 sale con 'Real' más de 8 puntos por debajo de 'Prometido', recorta esas probabilidades (o deja de recomendar ese mercado) y anótalo en notas_analista.md.
- Si sale por encima con n ≥ 20, el modelo es conservador ahí: puede pesar más que el mercado (65/35).
- Con n < 20, no cambies nada por esta tabla; úsala solo como alerta.
