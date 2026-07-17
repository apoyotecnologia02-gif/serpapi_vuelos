"""
Traduce las reglas de negocio a parametros NATIVOS de SerpApi.
Asi Google aplica los filtros y no traemos basura que despues descartamos.
 
Semantica de outbound_times / return_times (doc de SerpApi):
  "4,18"       -> salida 4:00 AM - 7:00 PM  (hora 4 hasta hora 18:59)
  "4,18,3,19"  -> salida 4:00 AM - 7:00 PM, llegada 3:00 AM - 8:00 PM
  El segundo numero N significa "hasta las N:59".
"""


def construir_times(llegada_ida_max_h=13, salida_regreso_min_h=16):
    """
    Reglas aVioa (por los traslados de 7am y 4pm):
      - IDA: debe LLEGAR al destino maximo a la 1:00 pm  -> llegada hasta 12:59
      - REGRESO: debe SALIR del destino desde las 4:00 pm -> salida 16:00 en adelante
    Devuelve (outbound_times, return_times) listos para la API.
    """
    outbound = f"0,23,0,{llegada_ida_max_h - 1}"   # salida libre, llegada hasta (h-1):59
    retorno = f"{salida_regreso_min_h},23"         # salida del regreso desde h
    return outbound, retorno
 
 
def construir_stops(destino):
    """
    stops de SerpApi:
      0 - cualquiera (default)   1 - solo sin escalas
      2 - 1 escala o menos       3 - 2 escalas o menos
    Con FILTRAR_ESCALAS=false devuelve 0 (no filtra: entran las conexiones,
    que suelen ser mas baratas pero mucho mas largas).
    Prioridad: max_escalas explicito del destino > regla por tipo.
    """
    from config.settings import FILTRAR_ESCALAS
    if not FILTRAR_ESCALAS:
        return 0
    explicito = destino.get("max_escalas")
    if explicito is not None:
        return {0: 1, 1: 2, 2: 3}.get(explicito, 3)
    return 1 if destino.get("tipo") == "NACIONAL" else 2
 
 
def params_busqueda(destino, origen, ida, regreso, moneda="COP", reglas=None):
    """Params completos de una busqueda round-trip con los filtros ya aplicados por Google."""
    reglas = reglas or {}
    out_t, ret_t = construir_times(
        reglas.get("llegada_ida_max_h", 13),
        reglas.get("salida_regreso_min_h", 16),
    )
    p = {
        "engine": "google_flights",
        "departure_id": origen,
        "arrival_id": destino["code"],
        "outbound_date": ida,
        "return_date": regreso,
        "type": 1,
        "currency": moneda,
        "gl": "co",
        "hl": "es",
        "sort_by": 2,                 # por precio (ya no ordenamos a mano)
        "stops": construir_stops(destino),
        "outbound_times": out_t,
        "return_times": ret_t,
        "deep_search": True,
        # include_airlines: restringe a esas aerolineas (ej. P5 = Wingo/Copa Colombia)
        "include_airlines": destino.get("aerolineas"),
    }

    return {k: v for k, v in p.items() if v is not None}

