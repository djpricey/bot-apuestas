# Notas del analista (leer antes de cada corrida)

## Pedidos pendientes del usuario
- (ninguno)

## Lecciones de método
- ESCALERA: busca en TODOS los mercados con cuota 1.25–1.60 (córners y tarjetas totales y por equipo, doble oportunidad, goles, hándicap), no solo 1X2 y goles. El 24-nov se dijo "no hay escalón" mirando solo 1X2/goles y el usuario lo cuestionó con razón. Prioriza partidos de la misma liga (sin sesgo de datos).
- ESCALERA, REGLA NUEVA (26-nov, pedido del usuario: "es diario, sin forzar"): NO exigir la cuota mínima de valor (1.04/p). En 1.25–1.60 BetPlay cobra 5–7 % de margen y esa regla casi nunca se cumple (mar 24 Hibernian fue el escalón 8; mié y jue quedaron sin escalón). La escalera usa la regla de "más probables": probabilidad ≥ 70 % (Pinnacle sin margen o modelo respaldado) y EV ≥ −3 %, es decir cuota mínima = 0.97/p. Dar SIEMPRE un escalón diario si alguno la cumple; decir "no hay" solo si ninguno de todos los mercados la cumple.
- Estadísticas domésticas en copas europeas: los equipos que dominan ligas débiles (Galatasaray, PSV, Feyenoord, Porto, AEK, Brujas, Olympiakos, Celtic) tienen "a favor" inflado y "en contra" bajo. Contra rivales de Champions eso NO se sostiene. Ejemplo: Galatasaray saca 7.2 córners en casa en Turquía, pero en la Champions pasada promedió 4 por partido y esta temporada remata ~8 por partido. Antes de usar datos domésticos en copas, búscale al equipo sus números en la competición (uefa.com/.../clubs/ID/statistics, Squawka, FotMob).
- Patrón: el modelo doméstico casi siempre da "más córners" para el equipo inferior y "menos tarjetas" en Champions; el mercado tiene razón en general (los árbitros UEFA sacan ~4 amarillas por partido, más que Serie A/Eredivisie esta temporada). Trátalo como sesgo, no como ventaja.
- Tiros, tiros a puerta y atajadas: las cifras de football-data (HS/HST) no coinciden con Opta (con lo que liquida BetPlay); el modelo sale sesgado a "menos". No apostar esos mercados sin datos Opta de la temporada.
- Donde el sesgo juega A FAVOR (equipo grande contra rival claramente más débil que su liga) o donde ambos equipos son de ligas top, los datos domésticos sí sirven.

- Antes de usar córners de liga en Europa League/Conference, mira los de la propia copa en uefa.com/uefaeuropaleague/clubs/ID/statistics: el 24-nov Celta (3.4 en casa en LaLiga) sacaba 7.75 por partido en la EL y Bournemouth 6.5; el "menos de 9.5" era un error.
- Si los datos de la copa y los de liga se contradicen (Dortmund 9 córners fuera en UCL vs Arsenal que concede 2.9 en casa; Slovan 1.5 en UCL vs Betis que concede 6.3 fuera), no se va contra el mercado.
- La página (index.html) solo muestra en la pestaña Partidos los partidos con la fecha MÁS ALTA de partidos[]. Pon ahí solo los del día D; los de días siguientes van en otros_partidos ("Mañana ..." / "Jue 26 ...").
- Pinnacle vía hoy.json solo cubre copas; para ligas domésticas no hay precio de referencia: usa el promedio modelo + BetPlay sin margen y el log de cuotas_ahora (los logs se leen con get_job_logs; la descarga directa de logs está bloqueada).

- El comparador del bot (errores.json) puede emparejar el partido equivocado: el 25-nov marcó Atlético–Viking "ambos marcan NO" a 2.18 (+16 %) con cuotas del partido SUB-19 (pocas decenas de mercados y "Total Goals by Atlético Madrid U19"). Si n_mercados es muy bajo para un partido grande, verifica con cuotas_ahora "ruta:..." antes de usarlo.
- Tras recalcular el escáner con promedio simple y promediar con BetPlay, casi todo queda entre -3 % y +4 %: las "ventajas" de 15-45 % del escáner son humo. Las únicas líneas que se acercan al mínimo suelen ser colas (cuotas 2.3+) con muestras de 4 partidos de copa: no publicarlas.
- No ir a "más córners" de un equipo que viene de una goleada grave en su último partido (Dundee 0-8 → 3 córners el 24-nov): el mercado lo descuenta mejor que los últimos 10.
- Para republicar la página: Artifact read sin path (guarda el HTML completo), leerlo entero y publicar ese archivo como file_path con files {"data.json": ...}.

- Cuotas largas (4.0+): quitar el margen de Pinnacle en partes iguales (proporcional) infla la probabilidad de los "longshots" y fabrica ventajas falsas (26-nov: menos de 1.5 goles a 7.00 en Lyon y Beşiktaş, Ajax pierde a 15, más de 4.5 goles en Olympiakos–Milan). Para cuotas largas usa el método potencia (p_i = (1/o_i)^k con k tal que sumen 1) antes de calcular EV; con eso casi todas desaparecen.
- Antes de "Milan/Juve menos córners": mira también si el equipo está obligado a ganar en la tabla de la fase de liga (Milan 28.º el 26-nov) y separa casa/fuera en la propia copa (la media de 4 partidos la infla un solo partido en casa).

## Candidatos vistos el 23-nov 11 p. m. (re-verificar cuotas, alineaciones y árbitro)
- Jue 26 Olympiakos–Milan: Milan menos de 3.5 córners (2.08) / menos de 4.5 (1.55). Milan saca solo 3.0 córners fuera en Serie A.
- Jue 26 Celta–Bournemouth: DESCARTADO el 24-nov (en la EL los dos sacan muchos córners).
- Jue 26 Juventus–Omonia: Juventus más de 6.5 córners (1.98). Juve saca 7.5 en casa en Serie A; Omonia es más débil (sesgo a favor). Ojo a rotaciones.
- Jue 26 NEC–Rennes: NEC más de 4.5 córners (1.88). NEC saca 7.6 en casa; Rennes concede 5.2 fuera.
- Jue 26 Crystal Palace–Real Sociedad: Real Sociedad más de 4.5 córners (1.93).
- Mar 24 / Mié 25: 1X2, goles y ambos marcan de Champions sin valor contra Pinnacle (BetPlay paga por debajo en todo). Rechazados por sesgo: Galatasaray más córners, Lens más córners, Napoli/Roma más córners, menos tarjetas en Inter–Stuttgart y Feyenoord–Porto, menos córners de Real Madrid.
- Árbitros de la jornada 5 de Champions sin publicar al 23-nov 11 p. m.

- Jue 26 Crystal Palace–Real Sociedad: Real Sociedad más de 4.5 córners (1.93) quedó en la soñadora del 24-nov. Revisar alineaciones y la cuota el jueves.

## Aprendizaje diario (desde 26-nov)
- Después de liquidar el día anterior (paso 2), corre `python -m src.calibracion RUTA/data.json` (el data.json ya actualizado) y lee `docs/calibracion.md` ANTES de analizar. Haz commit de calibracion.md.
- Aplica sus reglas: grupo con n ≥ 20 y acierto real 8+ puntos bajo lo prometido → recorta esas probabilidades o deja ese mercado; n < 20 → solo alerta, pero dilo en los avisos.
- Alerta al 26-nov: "córners menos" va 1 de 5 (prometía 69 %). Hasta que haya más casos, exige más margen en "menos córners" de un equipo, sobre todo si ese equipo necesita ganar o va de favorito.
- Cada error nuevo (dato malo, sesgo, regla mal aplicada) se anota aquí con fecha, en una línea, para no repetirlo.
- 26-nov: la corrida soltó Milan menos de 3.5 córners (1.95, mínimo 1.89) y Real Sociedad más de 4.5 córners, y los dos se dieron (Milan 1 córner, RS 7). Regla: si un pick del día anterior sigue en o por encima de su mínimo, no lo quites solo porque bajó la cuota; quítalo únicamente con un dato nuevo concreto (baja, alineación, árbitro) y dilo.

## ESCALONES 10 A 13 (meta ampliada a 2 millones, 26-nov): MODO CUIDADOSO
Pedido del usuario: "seamos más cuidadosos con los siguientes 4 escalones". Hoy (esc. 9) se ganó a un gol de perder. Para estos 4 escalones, por encima de la regla general de escalera:
1. Probabilidad ≥ 75 % y con DOS fuentes de acuerdo: Pinnacle sin margen ≥ 72 % Y modelo/datos propios ≥ 75 %. Por la calibración (el tramo 1.25–1.60 promete 74 % y acierta 55 %), réstale 5 puntos a tu probabilidad antes de comparar.
2. Colchón: la línea debe quedar lejos de lo esperado. Ej.: goles esperados 2.4 → no "menos de 3.5" (un gol tardío lo tumba); mejor "menos de 4.5" o mercado de un equipo. En córners/tarjetas, la línea a 2+ unidades del promedio esperado.
3. Evitar: partidos donde alguien necesita remontar o ganar sí o sí (sube el riesgo de goles/córners tardíos), cruces de ligas de distinto nivel (sesgo de copas), árbitro desconocido en tarjetas, datos de menos de 6 partidos.
4. Preferir partidos con alineación o árbitro ya confirmados y avisar al usuario que lo revise 1 hora antes.
5. Si nada cumple, NO hay escalón ese día: decirlo con los 2–3 candidatos más cercanos y por qué fallan. La escalera es diaria, pero en estos 4 escalones se permite saltar días.
6. Recordar al usuario la protección sugerida: al ganar el escalón 10, retirar los 20,000 iniciales y parte de la ganancia.

- 27-nov: escalón 10 saltado (modo cuidadoso): ninguna línea 1.25–1.60 tenía 75 % con dos fuentes y colchón. Lección: en ligas sin Pinnacle, revisa los marcadores reales de los últimos partidos de la misma fase (Bucaramanga 5 y 4 goles en cuadrangulares) antes de proponer "menos de 3.5" de escalera aunque BetPlay dé 74 %.
- 27-nov: antes de publicar un "más goles" por promedios de temporada, contrástalo con un modelo externo (Sports Mole/Opta) y con la cuota: el revisor tumbó Groningen–Willem II más de 3.5 (2.12) porque el 50 % propio era optimista.

- 28-nov: hoy.json ya trae Pinnacle para ligas domésticas (Premier, Championship, Serie A, Ligue 1, MLS, Liga MX, Brasil, Argentina). Usar Pinnacle (método potencia) como ancla en esas ligas; la nota de arriba sobre "Pinnacle solo copas" quedó vieja.
- 28-nov: antes de usar una media de córners de casa, mira si la infla un solo partido (Preston 5.6 con un 16 contra Lincoln → 4.1 sin él; Angers 6.0 con un 12). Usa mediana o quita el atípico.
- 28-nov: MLS ronda 1 (al mejor de 3): el local del partido 2 perdió el 1 y está obligado; los "menos de 4.5 goles" a 1.25–1.32 no sirven para la escalera cuidadosa.
- 28-nov: escalón 10 saltado otra vez (2.º día). Si mañana tampoco hay, dilo igual: la regla del modo cuidadoso permite saltar días.

## PEDIDO DEL USUARIO PARA EL DOMINGO 29-NOV (hecho el sábado 4 a. m.)
"Revisa todo lo que haya mañana": revisión a fondo de TODOS los partidos del domingo, todos los mercados (1X2, doble oportunidad, goles, ambos marcan, hándicaps, córners y tarjetas totales y por equipo). Incluir sí o sí los partidos colombianos (Medellín–Once Caldas y el resto de cuadrangulares del domingo) con árbitro designado y su promedio (valuestats), y la Liguilla MX. Para tarjetas en Colombia, el árbitro pesa mucho (ej. 27-nov: árbitro de 6.5 amarillas → más de 6.5 tarjetas ganó). Buscar escalón 10 en modo cuidadoso. Borrar este bloque cuando quede hecho.
