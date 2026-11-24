# Notas del analista (leer antes de cada corrida)

## Pedidos pendientes del usuario
- (ninguno)

## Lecciones de método
- ESCALERA: busca en TODOS los mercados con cuota 1.25–1.60 (córners y tarjetas totales y por equipo, doble oportunidad, goles, hándicap), no solo 1X2 y goles. El 24-nov se dijo "no hay escalón" mirando solo 1X2/goles y el usuario lo cuestionó con razón. Prioriza partidos de la misma liga (sin sesgo de datos).
- Estadísticas domésticas en copas europeas: los equipos que dominan ligas débiles (Galatasaray, PSV, Feyenoord, Porto, AEK, Brujas, Olympiakos, Celtic) tienen "a favor" inflado y "en contra" bajo. Contra rivales de Champions eso NO se sostiene. Ejemplo: Galatasaray saca 7.2 córners en casa en Turquía, pero en la Champions pasada promedió 4 por partido y esta temporada remata ~8 por partido. Antes de usar datos domésticos en copas, búscale al equipo sus números en la competición (uefa.com/.../clubs/ID/statistics, Squawka, FotMob).
- Patrón: el modelo doméstico casi siempre da "más córners" para el equipo inferior y "menos tarjetas" en Champions; el mercado tiene razón en general (los árbitros UEFA sacan ~4 amarillas por partido, más que Serie A/Eredivisie esta temporada). Trátalo como sesgo, no como ventaja.
- Tiros, tiros a puerta y atajadas: las cifras de football-data (HS/HST) no coinciden con Opta (con lo que liquida BetPlay); el modelo sale sesgado a "menos". No apostar esos mercados sin datos Opta de la temporada.
- Donde el sesgo juega A FAVOR (equipo grande contra rival claramente más débil que su liga) o donde ambos equipos son de ligas top, los datos domésticos sí sirven.

- Antes de usar córners de liga en Europa League/Conference, mira los de la propia copa en uefa.com/uefaeuropaleague/clubs/ID/statistics: el 24-nov Celta (3.4 en casa en LaLiga) sacaba 7.75 por partido en la EL y Bournemouth 6.5; el "menos de 9.5" era un error.
- Si los datos de la copa y los de liga se contradicen (Dortmund 9 córners fuera en UCL vs Arsenal que concede 2.9 en casa; Slovan 1.5 en UCL vs Betis que concede 6.3 fuera), no se va contra el mercado.
- La página (index.html) solo muestra en la pestaña Partidos los partidos con la fecha MÁS ALTA de partidos[]. Pon ahí solo los del día D; los de días siguientes van en otros_partidos ("Mañana ..." / "Jue 26 ...").
- Pinnacle vía hoy.json solo cubre copas; para ligas domésticas no hay precio de referencia: usa el promedio modelo + BetPlay sin margen y el log de cuotas_ahora (los logs se leen con get_job_logs; la descarga directa de logs está bloqueada).

## Candidatos vistos el 23-nov 11 p. m. (re-verificar cuotas, alineaciones y árbitro)
- Jue 26 Olympiakos–Milan: Milan menos de 3.5 córners (2.08) / menos de 4.5 (1.55). Milan saca solo 3.0 córners fuera en Serie A.
- Jue 26 Celta–Bournemouth: DESCARTADO el 24-nov (en la EL los dos sacan muchos córners).
- Jue 26 Juventus–Omonia: Juventus más de 6.5 córners (1.98). Juve saca 7.5 en casa en Serie A; Omonia es más débil (sesgo a favor). Ojo a rotaciones.
- Jue 26 NEC–Rennes: NEC más de 4.5 córners (1.88). NEC saca 7.6 en casa; Rennes concede 5.2 fuera.
- Jue 26 Crystal Palace–Real Sociedad: Real Sociedad más de 4.5 córners (1.93).
- Mar 24 / Mié 25: 1X2, goles y ambos marcan de Champions sin valor contra Pinnacle (BetPlay paga por debajo en todo). Rechazados por sesgo: Galatasaray más córners, Lens más córners, Napoli/Roma más córners, menos tarjetas en Inter–Stuttgart y Feyenoord–Porto, menos córners de Real Madrid.
- Árbitros de la jornada 5 de Champions sin publicar al 23-nov 11 p. m.

- Jue 26 Crystal Palace–Real Sociedad: Real Sociedad más de 4.5 córners (1.93) quedó en la soñadora del 24-nov. Revisar alineaciones y la cuota el jueves.
