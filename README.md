# Bot de apuestas · modelo que aprende solo

Cada día a las 6:00 a. m. (hora Colombia) GitHub corre este programa gratis:

1. **Descarga** los resultados y las cuotas de todas las ligas configuradas (football-data.co.uk).
2. **Re-ajusta** la fuerza de ataque y defensa de cada equipo con todos los partidos, dando más peso a los recientes.
3. **Se califica**: compara sus predicciones pasadas con lo que de verdad pasó y con el mercado.
4. **Aprende** cuánto "olvidar" del pasado y cuánto confiar en sí mismo frente a las cuotas, liga por liga.
5. **Publica** las probabilidades de los próximos 7 días en `docs/data/hoy.json`.

No usa créditos de Claude: solo matemáticas.

## Archivos que produce
- `docs/data/hoy.json`: próximos partidos con probabilidades (modelo, mercado y combinada) y posibles apuestas de valor.
- `docs/data/evaluacion.json`: récord en vivo y prueba con la última temporada, por liga.
- `docs/data/fuerzas.json`: ranking de equipos por liga.
- `docs/data/predicciones/`: la foto de cada día, para calificarla después.

## Correrlo a mano
Pestaña **Actions** → *Actualización diaria* → **Run workflow**.

## Ligas
Ver `src/config.py`. Liga BetPlay todavía no: no hay fuente gratuita con historial y cuotas.
