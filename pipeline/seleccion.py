"""
Decide que mostrarle al equipo: si el precio es bueno y por quien se compra.
 
Dos reglas de negocio de aVioa:
  1. Solo AEROLINEA DIRECTA (nada de Kiwi/Gotogate: el precio cambia al pasar
     a la aerolinea y no es seguro emitir por terceros).
  2. Es ganga si Google dice que el precio esta por debajo de lo tipico.
"""
 
def rango_tipico(insights):
    """(piso, techo) del mercado de la ruta. (None, None) si no hay insights."""
    r = (insights or {}).get("typical_price_range") or []
    return (r[0], r[1]) if len(r) >= 2 else (None, None)
 
 
def veredicto(precio, rango):
    """
    Barato / Normal / Caro comparando NUESTRO precio (ya filtrado) contra el
    rango tipico del MERCADO de la ruta.
 
    OJO: no se usa el price_level que devuelve Google, porque ese se refiere al
    precio mas barato de SU busqueda (sin nuestros filtros), no al nuestro.
    """
    piso, techo = rango if rango else (None, None)
    if not precio or piso is None or techo is None:
        return ""
    if precio < piso:
        return "Barato"
    if precio <= techo:
        return "Normal"
    return "Caro"
 
 
def pct_vs_piso(precio, rango):
    """Cuanto esta por debajo (+) o por encima (-) del piso tipico de la ruta."""
    piso = (rango or (None, None))[0]
    if not precio or not piso:
        return None
    return round((piso - precio) / piso * 100, 1)
 
 
def es_ganga(precio, rango, margen_pct=0.0):
    """Ganga = por debajo del piso tipico del mercado de la ruta."""
    piso = (rango or (None, None))[0]
    if not precio or not piso:
        return False
    return precio < piso * (1 - margen_pct / 100)
 
 
def elegir_vendedor(booking_options):
    """
    De booking_options devuelve el mas barato que sea AEROLINEA DIRECTA.
    None si solo hay terceros -> ese paquete no se muestra.
 
    En la respuesta de SerpApi, together.airline == True marca que el vendedor
    es la aerolinea y no una OTA.
    """
    directas = []
    for op in booking_options or []:
        j = op.get("together") or {}
        if not j.get("airline"):
            continue
        precio = j.get("price")
        if not precio:
            continue
        directas.append({
            "vendedor": j.get("book_with"),
            "precio": precio,
            "es_aerolinea": True,
            "separate_tickets": bool(op.get("separate_tickets")),
            "equipaje": ", ".join(j.get("baggage_prices") or []),
        })
    if not directas:
        return None
    return min(directas, key=lambda v: v["precio"])
 
 
def _hhmm(dt):
    """'2026-09-21 08:50' -> '08:50'."""
    return (dt or "")[-5:] if dt else ""
 
 
def detalle_tramo(vuelo_grupo):
    """Resume un itinerario (lista de segmentos) en campos planos para el Sheet."""
    vuelos = (vuelo_grupo or {}).get("flights") or []
    if not vuelos:
        return {}
    primero, ultimo = vuelos[0], vuelos[-1]
    dur = vuelo_grupo.get("total_duration") or 0
    return {
        "aerolinea": " / ".join(sorted({v.get("airline") for v in vuelos if v.get("airline")})),
        "numero_vuelo": " + ".join(v.get("flight_number", "") for v in vuelos),
        "salida": (primero.get("departure_airport") or {}).get("time"),
        "llegada": (ultimo.get("arrival_airport") or {}).get("time"),
        "escalas": len(vuelos) - 1,
        "duracion": f"{dur // 60}h {dur % 60:02d}m" if dur else "",
    }