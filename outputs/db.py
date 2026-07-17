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
  vendedor TEXT, precio_vendedor REAL,
  aerolinea_ida TEXT, aerolinea_regreso TEXT,
  escalas_ida INTEGER, escalas_regreso INTEGER,
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
        "nivel,piso,techo,pct_vs_piso,ganga,vendedor,precio_vendedor,aerolinea_ida,"
        "aerolinea_regreso,escalas_ida,escalas_regreso,link) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),
         o["origen"], o["destino"], o["ida"], o["regreso"], o.get("noches"),
         o.get("precio"), o.get("moneda"), o.get("nivel"),
         (o.get("rango") or [None, None])[0], (o.get("rango") or [None, None])[1],
         o.get("pct_vs_piso"), 1 if o.get("ganga") else 0,
         o.get("vendedor"), o.get("precio_vendedor"),
         o.get("aerolinea_ida"), o.get("aerolinea_regreso"),
         o.get("escalas_ida"), o.get("escalas_regreso"), o.get("link")))
    con.commit()