"""SQLite: historial de precios + TTL para no re-escanear lo mismo."""
import sqlite3
from datetime import datetime, timedelta, timezone

from config.settings import DB

DDL = """
CREATE TABLE IF NOT EXISTS ofertas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  visto_en TEXT NOT NULL,
  origen TEXT NOT NULL, destino TEXT NOT NULL,
  ida TEXT NOT NULL, regreso TEXT NOT NULL, noches INTEGER,
  precio REAL, moneda TEXT,
  nivel TEXT, piso REAL, techo REAL, pct_vs_piso REAL, ganga INTEGER,
  veredicto TEXT,
  vendedor TEXT, precio_vendedor REAL, equipaje TEXT, separate_tickets INTEGER,
  aerolinea_ida TEXT, vuelo_ida TEXT, salida_ida TEXT, llegada_ida TEXT,
  escalas_ida INTEGER, duracion_ida TEXT,
  aerolinea_regreso TEXT, vuelo_regreso TEXT, salida_regreso TEXT, llegada_regreso TEXT,
  escalas_regreso INTEGER, duracion_regreso TEXT,
  link TEXT
);
CREATE INDEX IF NOT EXISTS ix_ruta ON ofertas(origen, destino, ida, regreso);
CREATE INDEX IF NOT EXISTS ix_visto ON ofertas(visto_en);
"""


def abrir():
    con = sqlite3.connect(DB)
    con.executescript(DDL)
    return con


def reciente(con, origen, destino, ida, regreso, ttl_horas):
    """True si ya escaneamos ese par de fechas hace menos de ttl_horas."""
    corte = (datetime.now(timezone.utc) - timedelta(hours=ttl_horas)).isoformat()
    q = ("SELECT 1 FROM ofertas WHERE origen=? AND destino=? AND ida=? AND regreso=? "
         "AND visto_en > ? LIMIT 1")
    return con.execute(q, (origen, destino, ida, regreso, corte)).fetchone() is not None


def guardar(con, o):
    con.execute(
        "INSERT INTO ofertas (visto_en,origen,destino,ida,regreso,noches,precio,moneda,"
        "nivel,piso,techo,pct_vs_piso,ganga,veredicto,"
        "vendedor,precio_vendedor,equipaje,separate_tickets,"
        "aerolinea_ida,vuelo_ida,salida_ida,llegada_ida,escalas_ida,duracion_ida,"
        "aerolinea_regreso,vuelo_regreso,salida_regreso,llegada_regreso,"
        "escalas_regreso,duracion_regreso,link) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),
         o["origen"], o["destino"], o["ida"], o["regreso"], o.get("noches"),
         o.get("precio"), o.get("moneda"), o.get("nivel"),
         (o.get("rango") or [None, None])[0], (o.get("rango") or [None, None])[1],
         o.get("pct_vs_piso"), 1 if o.get("ganga") else 0, o.get("veredicto"),
         o.get("vendedor"), o.get("precio_vendedor"),
         o.get("equipaje"), 1 if o.get("separate_tickets") else 0,
         o.get("aerolinea_ida"), o.get("vuelo_ida"),
         o.get("salida_ida"), o.get("llegada_ida"),
         o.get("escalas_ida"), o.get("duracion_ida"),
         o.get("aerolinea_regreso"), o.get("vuelo_regreso"),
         o.get("salida_regreso"), o.get("llegada_regreso"),
         o.get("escalas_regreso"), o.get("duracion_regreso"),
         o.get("link")))
    con.commit()