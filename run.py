"""
Monitor de vuelos

Flujo por destino:
  1. google_flights_deals con ventana flexible -> fechas mas baratas (1 request)
  2. google_flights round-trip con filtros NATIVOS (horarios, escalas, orden) por fecha
  3. booking_token -> vendedor; solo se muestra si es AEROLINEA DIRECTA
  4. Sheets (lo nuevo arriba, gangas en verde) + SQLite (historial)
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import (SERPAPI_KEY, MONEDA, REGLAS, TOPE_CORRIDA, PAUSA_SEG,
                             MESES_EXPLORE, CONFIRMAR_TOP, SOLO_GANGAS, TIMEOUT_SEG,
                             TTL_HORAS, destinos_de_hoy,
                             meses_a_explorar, IATAS)
from serpapi_client.client import (Cliente, CuotaAgotada, ErrorSerp,
                                   SinResultados)
from serpapi_client.flights import (explorar_mes, fechas_de_explore, buscar_paquete,
                                    traer_regreso, traer_booking, traer_insights)
from pipeline.seleccion import (rango_tipico, veredicto, pct_vs_piso, es_ganga,
                                elegir_vendedor, detalle_tramo)
from outputs import sheets
from outputs.db import abrir, reciente, guardar


def _candidatas(cli, destino, origen, meses):
    """
    Etapa 1 (brujula): explore por mes -> la ventana barata de cada uno.
    1 request por mes. Devuelve pares (ida, regreso) unicos, mas barato primero.
    """
    noches = destino.get("noches", 3)
    vistos, salida = set(), []
    for mes in meses:
        try:
            datos = explorar_mes(cli, destino, origen, mes, MONEDA)
        except SinResultados:
            continue                       # ese mes no tiene vuelos; normal
        except ErrorSerp as e:
            print(f"  explore mes {mes} fallo ({e}); sigo")
            continue
        c = fechas_de_explore(datos, noches)
        if not c or (c["ida"], c["regreso"]) in vistos:
            continue
        vistos.add((c["ida"], c["regreso"]))
        salida.append(c)
    # explore ya rankeo por precio estimado: solo confirmamos las mas baratas,
    # porque confirmar cuesta 4 requests y explorar solo 1.
    salida.sort(key=lambda x: x["precio_est"] or 1e12)
    return salida[:CONFIRMAR_TOP]


def _procesar(cli, con, destino, ida, regreso):
    """Confirma un par de fechas y devuelve la oferta lista, o None si no sirve."""
    origen = destino["origin"]
    datos = buscar_paquete(cli, destino, origen, ida, regreso, MONEDA, REGLAS)

    vuelos = (datos.get("best_flights") or []) + (datos.get("other_flights") or [])
    if not vuelos:
        return None
    mejor = min(vuelos, key=lambda v: v.get("price") or 1e12)
    precio = mejor.get("price")
    if not precio:
        return None

    o = {
        "origen": origen, "destino": destino["code"], "hoja": destino["name"],
        "ida": ida, "regreso": regreso, "noches": destino.get("noches"),
        "precio": precio, "moneda": MONEDA,
        "link": (datos.get("search_metadata") or {}).get("google_flights_url", ""),
    }
    di = detalle_tramo(mejor)
    o.update({"aerolinea_ida": di.get("aerolinea"), "vuelo_ida": di.get("numero_vuelo"),
              "salida_ida": di.get("salida"), "llegada_ida": di.get("llegada"),
              "escalas_ida": di.get("escalas"), "duracion_ida": di.get("duracion")})

    # ── vendedor: exige AEROLINEA DIRECTA (regla de negocio) ──
    tok = mejor.get("departure_token")
    if not tok:
        return None
    reg_datos = traer_regreso(cli, destino, origen, ida, regreso, tok, MONEDA, REGLAS)
    vuelta = ((reg_datos.get("best_flights") or []) + (reg_datos.get("other_flights") or []))
    if not vuelta:
        return None
    v_mejor = min(vuelta, key=lambda v: v.get("price") or 1e12)
    dv = detalle_tramo(v_mejor)
    o.update({"aerolinea_regreso": dv.get("aerolinea"), "vuelo_regreso": dv.get("numero_vuelo"),
              "salida_regreso": dv.get("salida"), "llegada_regreso": dv.get("llegada"),
              "escalas_regreso": dv.get("escalas"), "duracion_regreso": dv.get("duracion")})

    btok = v_mejor.get("booking_token")
    if not btok:
        return None
    book = traer_booking(cli, destino, origen, ida, regreso, btok, MONEDA)
    vend = elegir_vendedor(book.get("booking_options"))
    if not vend:
        return None                                  # solo terceros -> no se muestra
    o.update({"vendedor": vend["vendedor"], "precio_vendedor": vend["precio"],
              "equipaje": vend.get("equipaje", ""),
              "separate_tickets": vend.get("separate_tickets")})

    # ── referencia del mercado: request PELADA (los filtros matan price_insights) ──
    # va al final a proposito: solo se gasta en paquetes que ya pasaron todo.
    rango = rango_tipico(traer_insights(cli, destino, origen, ida, regreso, MONEDA))
    o.update({"rango": list(rango) if rango[0] else None,
              "veredicto": veredicto(precio, rango),
              "nivel": veredicto(precio, rango),
              "pct_vs_piso": pct_vs_piso(precio, rango),
              "ganga": es_ganga(precio, rango)})
    return o


def main():
    t0 = time.time()
    cli = Cliente(SERPAPI_KEY, tope_corrida=TOPE_CORRIDA, pausa=PAUSA_SEG,
                  timeout=TIMEOUT_SEG)
    con = abrir()
    meses = meses_a_explorar()
    del_dia = destinos_de_hoy()
    print(f"Hoy: {len(del_dia)} destinos | explorando meses {meses} | tope {TOPE_CORRIDA} req")

    n_ofertas = n_gangas = n_destinos = 0
    for destino in del_dia:
        origen, code = destino["origin"], destino["code"]
        print(f"\n==== {origen} -> {code} ({destino['name']}) ====")
        try:
            cands = _candidatas(cli, destino, origen, meses)
            if not cands:
                print("  explore no devolvio fechas")
                continue
            n_destinos += 1
            print(f"  fechas candidatas: {[(c['ida'], c['precio_est']) for c in cands]}")

            for c in cands:
                if reciente(con, origen, code, c["ida"], c["regreso"], TTL_HORAS):
                    print(f"  {c['ida']}: ya escaneada hace <{TTL_HORAS:g}h (TTL); salto")
                    continue
                try:
                    o = _procesar(cli, con, destino, c["ida"], c["regreso"])
                except SinResultados:
                    print(f"  {c['ida']}: Google no trae vuelos que cumplan; salto la fecha")
                    continue
                except ErrorSerp as e:
                    print(f"  {c['ida']}: error ({e}); salto la fecha")
                    continue
                if not o:
                    print(f"  {c['ida']}: sin aerolinea directa que cumpla; salto")
                    continue
                guardar(con, o)          # el historial guarda todo, siempre
                if SOLO_GANGAS and not o["ganga"]:
                    print(f"  {o['ida']}: {o['precio']:,.0f} ({o['veredicto']}) "
                          f"no es ganga; no va al Sheet")
                    continue
                sheets.escribir(o)
                n_ofertas += 1
                n_gangas += 1 if o["ganga"] else 0
                marca = "  <<< GANGA" if o["ganga"] else ""
                print(f"  {o['ida']} / {o['regreso']} | {o['precio']:,.0f} {MONEDA} "
                      f"({o['veredicto']}) | {o['vendedor']}{marca}")

        except CuotaAgotada as e:
            print(f"\n[SIN CUOTA] {e}\n  Detengo la corrida.")
            break
        except ErrorSerp as e:
            print(f"  error SerpApi ({e}); salto el destino")
            continue
        except Exception as e:
            print(f"  fallo inesperado ({type(e).__name__}: {e}); salto el destino")
            continue

    r = cli.resumen()
    print(f"\n{'='*60}")
    print(f"Fin {datetime.now(ZoneInfo('America/Bogota')).strftime('%Y-%m-%d %H:%M')} | "
          f"{int(time.time()-t0)}s")
    print(f"destinos={n_destinos} ofertas={n_ofertas} gangas={n_gangas}")
    print(f"requests={r['gastadas']} | desglose={r['desglose']}")
    con.close()


if __name__ == "__main__":
    main()