"""Seleccion local para nacionales; no realiza solicitudes ni escribe Sheets."""
from datetime import datetime, time
from math import inf, isfinite


def _precio(v):
    p = v.get('price')
    return p if isinstance(p, (int, float)) and not isinstance(p, bool) and isfinite(p) and p > 0 else None


def desvio_horario(vuelo, tramo, fecha):
    segmentos = vuelo.get('flights') or []
    if not segmentos:
        return None
    campo = 'arrival_airport' if tramo == 'ida' else 'departure_airport'
    segmento = segmentos[-1] if tramo == 'ida' else segmentos[0]
    try:
        valor = (segmento.get(campo) or {}).get('time')
        instante = datetime.fromisoformat(valor)
        limite = datetime.combine(datetime.fromisoformat(fecha).date(), time(15))
        delta = (instante - limite if tramo == 'ida' else limite - instante).total_seconds() / 60
        return max(0, delta) if delta != 0 else 1 / 60
    except (ValueError, TypeError):
        return None


def seleccionar_vuelo(vuelos, destino, tramo, fecha, rango=None):
    """Baratos+horario: menor precio. Si no, baratos mas cercanos.

    Buen precio = <= piso tipico; sin piso, minimo recibido. Si ninguno tiene
    buen precio, menor desvio entre todos; empate por precio. Horas ausentes
    al final. Sin explorar otros tokens ni agregar consultas.
    """
    validos = [v for v in vuelos if _precio(v) is not None]
    if not validos:
        return None
    if str(destino.get('tipo', '')).upper() != 'NACIONAL':
        return min(validos, key=lambda v: v['price'])
    minimo = min(v['price'] for v in validos)
    piso = (rango or (None, None))[0]
    if not isinstance(piso, (int, float)) or not isfinite(piso) or piso <= 0:
        piso = minimo
    baratos = [v for v in validos if v['price'] <= piso]
    ideales = [v for v in baratos if desvio_horario(v, tramo, fecha) == 0]
    if ideales:
        return min(ideales, key=lambda v: v['price'])
    def clave(v):
        desvio = desvio_horario(v, tramo, fecha)
        return (inf if desvio is None else desvio, v['price'])
    return min(baratos or validos, key=clave)
