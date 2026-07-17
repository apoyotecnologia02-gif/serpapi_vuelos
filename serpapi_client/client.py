"""Cliente SerpApi con contador de cuota, reintentos y manejo de 429.
"""
import time
from collections import Counter

import serpapi


class CuotaAgotada(Exception):
    """SerpApi devolvio 429: se acabaron las busquedas del plan."""


class ErrorSerp(Exception):
    """Cualquier otro fallo de SerpApi (no debe tumbar la corrida)."""


class SinResultados(ErrorSerp):
    """
    Google no devolvio vuelos para esa consulta. NO es un fallo: es una
    respuesta definitiva (esa ruta/fecha no tiene vuelos que cumplan los
    filtros). No se reintenta -> cada reintento seria un request pagado
    por la misma nada.
    """


# respuestas definitivas: no tiene sentido reintentarlas
_DEFINITIVAS = ("hasn't returned any results", "has not returned any results")


def _limpio(params):
    """Params sin secretos, para logs. La libreria inyecta api_key en el dict."""
    return {k: v for k, v in (params or {}).items()
            if k not in ("api_key", "departure_token", "booking_token")}


class Cliente:
    def __init__(self, api_key, tope_corrida=200, pausa=1.0, timeout=90, log=print):
        if not api_key:
            raise SystemExit("Falta SERPAPI_KEY en el .env")
        self.tope_corrida = tope_corrida
        self.pausa = pausa
        self.log = log
        self.gastadas = 0
        self.desglose = Counter()
        self.cliente = serpapi.Client(api_key=api_key, timeout=timeout)

    def buscar(self, params, tipo="search", intentos=3):
        """
        Llama a SerpApi y devuelve SerpResults (UserDict: .get() y [] funcionan).
        Cuenta la request. Lanza CuotaAgotada en 429, ErrorSerp si agota reintentos.
        """
        if self.gastadas >= self.tope_corrida:
            raise CuotaAgotada(f"tope de corrida alcanzado ({self.tope_corrida})")

        ultimo = None
        for i in range(intentos):
            try:
                time.sleep(self.pausa)
                r = self.cliente.search(dict(params))
                self.gastadas += 1
                self.desglose[tipo] += 1
                if r.get("error"):
                    err = str(r["error"])
                    if any(t in err.lower() for t in _DEFINITIVAS):
                        raise SinResultados(err)
                    raise ErrorSerp(err)
                return r
            except (CuotaAgotada, SinResultados):
                raise
            except Exception as e:
                msg = str(e)
                if "429" in msg or "run out" in msg.lower():
                    raise CuotaAgotada(msg) from e
                ultimo = e
                if i < intentos - 1:
                    espera = 5 * (i + 1)          # 5s, luego 10s
                    self.log(f"      reintento {i+2}/{intentos} en {espera}s "
                             f"({type(e).__name__}: {msg[:70]})")
                    self.log(f"      params: {_limpio(params)}")   # sin api_key
                    time.sleep(espera)

        raise ErrorSerp(f"[{tipo}] tras {intentos} intentos: {ultimo} | "
                        f"params={_limpio(params)}")

    def resumen(self):
        return {"gastadas": self.gastadas, "desglose": dict(self.desglose)}