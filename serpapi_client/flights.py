"""Las llamadas a SerpApi que necesita el pipeline.

Etapa 1 (brujula): google_travel_explore con arrival_id -> que ventana esta barata.
Etapa 2 (precision): google_flights round-trip con las noches exactas y los
                     filtros nativos (horarios, escalas, orden por precio).
"""
from datetime import date, timedelta

from pipeline.filtros import params_busqueda, construir_stops


def _duracion_explore(noches):
    """
    travel_duration de explore solo acepta:
      1 - fin de semana | 2 - 1 semana (default) | 3 - 2 semanas
    No acepta noches exactas: se usa como aproximacion para hallar la ventana
    barata. Las noches reales se aplican despues en google_flights.
    """
    if noches <= 3:
        return 1        # fin de semana
    if noches <= 8:
        return 2        # 1 semana
    return 3            # 2 semanas


def explorar_mes(cli, destino, origen, mes, moneda="COP"):
    """
    google_travel_explore para UNA ruta y UN mes -> la ventana mas barata.
    Devuelve el dict crudo; trae start_date / end_date al nivel superior
    y la lista 'flights'. 1 request.
    """
    params = {
        "engine": "google_travel_explore",
        "departure_id": origen,
        "arrival_id": destino["code"],
        "type": 1,
        "month": mes,                                   # 1-12 (solo proximos 6 meses)
        "travel_duration": _duracion_explore(destino.get("noches", 3)),
        "travel_mode": 1,                               # solo vuelos
        "stops": construir_stops(destino),
        "currency": moneda,
        "gl": "co",
        "hl": "es",
        "include_airlines": destino.get("aerolineas"),
    }
    return cli.buscar({k: v for k, v in params.items() if v is not None}, tipo="explore")


def fechas_de_explore(datos, noches):
    """
    Saca (ida, regreso) del explore. El 'end_date' de explore corresponde a SU
    duracion (fin de semana / 1 semana), no a nuestras noches: por eso el
    regreso se recalcula con las noches reales del destino.
    """
    ida = datos.get("start_date")
    if not ida:
        return None
    try:
        regreso = (date.fromisoformat(ida) + timedelta(days=noches)).isoformat()
    except ValueError:
        return None
    vuelos = datos.get("flights") or []
    barato = min((v.get("price") for v in vuelos if v.get("price")), default=None)
    return {"ida": ida, "regreso": regreso, "precio_est": barato}


def buscar_paquete(cli, destino, origen, ida, regreso, moneda="COP", reglas=None):
    """Round-trip con TODOS los filtros aplicados por Google."""
    return cli.buscar(params_busqueda(destino, origen, ida, regreso, moneda, reglas),
                      tipo="search")


def traer_regreso(cli, destino, origen, ida, regreso, departure_token, moneda="COP", reglas=None):
    """
    Paso 2 del round-trip: los tramos de vuelta del itinerario ya elegido.
    Sin deep_search: aqui no aporta (el itinerario ya esta escogido) y hace que
    la llamada se demore hasta dar timeout.
    """
    p = params_busqueda(destino, origen, ida, regreso, moneda, reglas)
    p.pop("deep_search", None)
    p["departure_token"] = departure_token
    return cli.buscar(p, tipo="returns")


def traer_insights(cli, destino, origen, ida, regreso, moneda="COP"):
    """
    price_insights del MERCADO de la ruta: busqueda PELADA, sin filtros.

    Comprobado: con outbound_times/return_times/sort_by/deep_search, Google NO
    devuelve price_insights. Por eso va en request aparte. Ademas es lo correcto:
    el rango tipico debe reflejar el mercado, no nuestro subconjunto filtrado.
    """
    r = cli.buscar({
        "engine": "google_flights",
        "departure_id": origen,
        "arrival_id": destino["code"],
        "outbound_date": ida,
        "return_date": regreso,
        "type": 1,
        "currency": moneda,
        "gl": "co",
        "hl": "es",
    }, tipo="insights")
    return r.get("price_insights") or {}


def traer_booking(cli, destino, origen, ida, regreso, booking_token, moneda="COP"):
    """Quien vende y a que precio (aqui sale si es aerolinea directa)."""
    return cli.buscar({
        "engine": "google_flights",
        "departure_id": origen,
        "arrival_id": destino["code"],
        "outbound_date": ida,
        "return_date": regreso,
        "booking_token": booking_token,
        "currency": moneda,
        "gl": "co",
        "hl": "es",
    }, tipo="booking")