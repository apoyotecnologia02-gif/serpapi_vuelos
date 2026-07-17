"""Configuracion de aVioa: credenciales, reglas de negocio y destinos."""
import os
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

# ── credenciales ──
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SHEET_ID = os.getenv("SHEET_ID", "")
CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE", "client_secrets.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "token.json")
DB = os.getenv("DB", "vuelos.db")

# ── moneda / mercado ──
MONEDA, PAIS, IDIOMA = "COP", "co", "es"

# ── reglas de negocio (traslados de 7am y 4pm) ──
REGLAS = {
    "llegada_ida_max_h": int(os.getenv("LLEGADA_IDA_MAX_H", "13")),    # ida llega <= 1pm
    "salida_regreso_min_h": int(os.getenv("SALIDA_REGRESO_MIN_H", "16")),  # regreso sale >= 4pm
}

# Filtrar escalas encarece: quitarlo deja entrar vuelos con conexion (mas baratos
# pero mas largos). En false, Google devuelve cualquier cantidad de escalas y la
# columna "Escalas" del Sheet queda como el aviso para el asesor.
FILTRAR_ESCALAS = os.getenv("FILTRAR_ESCALAS", "true").lower() == "true"

# ── presupuesto ──
TOPE_CORRIDA = int(os.getenv("TOPE_CORRIDA", "200"))   # requests max por corrida
PAUSA_SEG = float(os.getenv("PAUSA_SEG", "1.0"))
TIMEOUT_SEG = int(os.getenv("TIMEOUT_SEG", "90"))   # deep_search puede tardar
# explorar es barato (1 request); confirmar es caro (4). Por eso: explorar ANCHO
# (los 6 meses que permite Google) y confirmar ANGOSTO (solo las mas baratas).
MESES_EXPLORE = int(os.getenv("MESES_EXPLORE", "6"))    # max 6: limite de Google
CONFIRMAR_TOP = int(os.getenv("CONFIRMAR_TOP", "2"))    # cuantas fechas confirmar
SOLO_GANGAS = os.getenv("SOLO_GANGAS", "false").lower() == "true"
TTL_HORAS = float(os.getenv("TTL_HORAS", "20"))        # no re-escanear lo mismo antes de esto

# ── ventana de busqueda ──
# explore solo cubre los proximos 6 meses; empezamos por el mes siguiente
# para no traer fechas demasiado cercanas (que ya no se alcanzan a vender).
MES_INICIAL_OFFSET = int(os.getenv("MES_INICIAL_OFFSET", "1"))


# Google cuenta el mes ACTUAL dentro de sus 6 meses: en julio la ventana valida
# es julio..diciembre (offsets 0..5). Pedir enero (offset 6) devuelve 400.
OFFSET_MAX = 5


def meses_a_explorar(hoy=None):
    """Lista de meses (1-12) a explorar, dentro de la ventana que permite Google."""
    hoy = hoy or date.today()
    salida = []
    for i in range(MES_INICIAL_OFFSET, MES_INICIAL_OFFSET + MESES_EXPLORE):
        if i > OFFSET_MAX:
            break
        m = hoy.month + i
        salida.append(m - 12 if m > 12 else m)
    return salida


TODOS = [0, 1, 2, 3, 4, 5, 6]

# max_escalas: solo donde la regla por tipo no aplica.
#   NACIONAL sin definir      -> solo directos
#   INTERNACIONAL sin definir -> hasta 1 escala
DESTINOS = [
    # ── DIARIOS — desde Medellin ──
    {"name": "Cartagena",     "code": "CTG", "origin": "MDE", "tipo": "NACIONAL",      "dias": TODOS, "noches": 2},
    {"name": "Santa Marta",   "code": "SMR", "origin": "MDE", "tipo": "NACIONAL",      "dias": TODOS, "noches": 2},
    {"name": "San Andres",    "code": "ADZ", "origin": "MDE", "tipo": "NACIONAL",      "dias": TODOS, "noches": 3},
    {"name": "Punta Cana",    "code": "PUJ", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": TODOS, "noches": 3},
    # OJO con "aerolineas": include_airlines EXCLUYE todo lo demas, no "prioriza".
    # Con P5 (Wingo/Copa Colombia) MDE->PTY devolvia CERO vuelos que cumplieran
    # los horarios, y el destino quedaba vacio. Descomentar solo si se confirma
    # que Wingo cubre la ruta con los horarios de aVioa.
    {"name": "Panama",        "code": "PTY", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": TODOS, "noches": 3},
    #  "aerolineas": "P5"},

    # ── 2 VECES POR SEMANA ──
    {"name": "Cancun",        "code": "CUN", "origin": "BOG", "tipo": "INTERNACIONAL", "dias": [0, 3], "noches": 3},
    {"name": "Curazao (4n)",  "code": "CUR", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [1, 4], "noches": 4},
    {"name": "Santo Domingo", "code": "SDQ", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [2, 5], "noches": 4},
    {"name": "Guajira",       "code": "RCH", "origin": "MDE", "tipo": "NACIONAL",      "dias": [0, 3], "noches": 3,
     "max_escalas": 1},   # sin vuelo directo desde MDE (confirmado)
    {"name": "Rio de Janeiro","code": "GIG", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [1, 4], "noches": 4},
    {"name": "Rio de Janeiro","code": "GIG", "origin": "BOG", "tipo": "INTERNACIONAL", "dias": [2, 5], "noches": 4},

    # ── 1 VEZ POR SEMANA — desde Medellin ──
    {"name": "Amazonas",        "code": "LET", "origin": "MDE", "tipo": "NACIONAL",      "dias": [0], "noches": 3,
     "max_escalas": 1},   # Leticia: conecta por Bogota
    {"name": "Curazao (3n)",    "code": "CUR", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [1], "noches": 3},
    {"name": "Jamaica",         "code": "MBJ", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [2], "noches": 3},
    {"name": "Buenos Aires",    "code": "EZE", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [3], "noches": 4},
    {"name": "Aruba",           "code": "AUA", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [4], "noches": 3},
    {"name": "Lima",            "code": "LIM", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [5], "noches": 5},
    {"name": "Orlando",         "code": "MCO", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [6], "noches": 4},
    {"name": "Cabos",           "code": "SJD", "origin": "MDE", "tipo": "INTERNACIONAL", "dias": [0], "noches": 4,
     "max_escalas": 2},
    {"name": "Santiago de Chile","code": "SCL","origin": "MDE", "tipo": "INTERNACIONAL", "dias": [1], "noches": 4},

    # ── 1 VEZ POR SEMANA — desde Bogota ──
    {"name": "Ciudad de Mexico","code": "MEX", "origin": "BOG", "tipo": "INTERNACIONAL", "dias": [2], "noches": 3},
    {"name": "Madrid (5n)",     "code": "MAD", "origin": "BOG", "tipo": "INTERNACIONAL", "dias": [3], "noches": 5},
    {"name": "Madrid (15n)",    "code": "MAD", "origin": "BOG", "tipo": "INTERNACIONAL", "dias": [4], "noches": 15},
    {"name": "Madrid (17n)",    "code": "MAD", "origin": "BOG", "tipo": "INTERNACIONAL", "dias": [5], "noches": 17},
    {"name": "Estambul",        "code": "IST", "origin": "BOG", "tipo": "INTERNACIONAL", "dias": [6], "noches": 9,
     "max_escalas": 2},   # sin directo desde Colombia
]

IATAS = {
    "CTG": "Cartagena", "SMR": "Santa Marta", "ADZ": "San Andres", "PUJ": "Punta Cana",
    "PTY": "Panama", "CUN": "Cancun", "CUR": "Curazao", "SDQ": "Santo Domingo",
    "RCH": "Guajira", "GIG": "Rio de Janeiro", "LET": "Amazonas", "MBJ": "Jamaica",
    "EZE": "Buenos Aires", "AUA": "Aruba", "LIM": "Lima", "MCO": "Orlando",
    "SJD": "Cabos", "SCL": "Santiago de Chile", "MEX": "Ciudad de Mexico",
    "MAD": "Madrid", "IST": "Estambul", "MDE": "Medellin", "BOG": "Bogota",
}


def destinos_de_hoy(hoy=None):
    hoy = hoy or date.today()
    return [d for d in DESTINOS if hoy.weekday() in d["dias"]]