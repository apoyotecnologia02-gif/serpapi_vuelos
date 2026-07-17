"""
Diagnostico: por que no llega price_insights.

Hace 2 requests a la MISMA ruta y fechas:
  A) con nuestros filtros (horarios, escalas, sort, deep_search)
  B) pelada (solo origen, destino, fechas)

Si A no trae price_insights y B si -> son los filtros.
Si ninguna lo trae -> Google no tiene historial de esa ruta.

Uso:  python diagnostico.py
"""
from config.settings import SERPAPI_KEY, MONEDA, REGLAS
from serpapi_client.client import Cliente
from pipeline.filtros import params_busqueda

DESTINO = {"code": "CTG", "tipo": "NACIONAL", "noches": 2, "name": "Cartagena"}
ORIGEN = "MDE"
IDA, REGRESO = "2026-09-24", "2026-09-26"


def mostrar(nombre, datos):
    print(f"\n--- {nombre} ---")
    print(f"  claves: {sorted(datos.keys())}")
    ins = datos.get("price_insights")
    print(f"  price_insights: {ins!r}")
    for k in ("best_flights", "other_flights"):
        print(f"  {k}: {len(datos.get(k) or [])} vuelos")
    vuelos = (datos.get("best_flights") or []) + (datos.get("other_flights") or [])
    if vuelos:
        p = min((v.get("price") for v in vuelos if v.get("price")), default=None)
        print(f"  precio mas barato: {p:,}" if p else "  sin precio")


def main():
    cli = Cliente(SERPAPI_KEY, tope_corrida=10, pausa=1.0)

    a = params_busqueda(DESTINO, ORIGEN, IDA, REGRESO, MONEDA, REGLAS)
    print(f"A) params con filtros: { {k: v for k, v in a.items() if k != 'engine'} }")
    mostrar("A) CON nuestros filtros", cli.buscar(a, tipo="dbg_a"))

    b = {"engine": "google_flights", "departure_id": ORIGEN, "arrival_id": DESTINO["code"],
         "outbound_date": IDA, "return_date": REGRESO, "type": 1,
         "currency": MONEDA, "gl": "co", "hl": "es"}
    print(f"\nB) params pelados: { {k: v for k, v in b.items() if k != 'engine'} }")
    mostrar("B) SIN filtros", cli.buscar(b, tipo="dbg_b"))

    print(f"\nrequests gastadas: {cli.resumen()['gastadas']}")
    print("\nLECTURA:")
    print("  A sin insights + B con insights -> los filtros los matan")
    print("  ninguna con insights            -> Google no tiene historial de la ruta")


if __name__ == "__main__":
    main()