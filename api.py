from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime, timedelta, timezone
from config.settings import DB

app = FastAPI(title="Vuelos Baratos API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"]
)

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

@app.get("/ofertas")
def ofertas(
    solo_gangas: bool = False,
    limit: int = Query(20, le=100),
    origen: str | None = None,
    destino: str | None = None,
    aerolinea: str | None = None,
    horas: int | None = None,
    precio_min: float | None = None,
    precio_max: float | None = None,
    max_escalas: int | None = None,
    fecha_ida_desde: str | None = None,
    fecha_ida_hasta: str | None = None
):
    con = get_db()
    sql = "SELECT * FROM ofertas WHERE 1=1"
    params: list = []

    if horas is not None:
        corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
        sql += " AND visto_en > ?"
        params.append(corte)

    if solo_gangas:
        sql += " AND ganga = 1"
    if origen:
        sql += " AND origen = ?"
        params.append(origen.upper())
    if destino:
        sql += " AND destino = ?"
        params.append(destino.upper())
    if aerolinea:
        sql += " AND (LOWER(aerolinea_ida) LIKE ? OR LOWER(aerolinea_regreso) LIKE ?)"
        like = f"%{aerolinea.lower()}%"
        params.extend([like, like])
    if precio_min is not None:
        sql += " AND precio >= ?"
        params.append(precio_min)
    if precio_max is not None:
        sql += " AND precio <= ?"
        params.append(precio_max)
    if max_escalas is not None:
        sql += " AND (escalas_ida IS NULL OR escalas_ida <= ?) AND (escalas_regreso IS NULL OR escalas_regreso <= ?)"
        params.extend([max_escalas, max_escalas])
    if fecha_ida_desde:
        sql += " AND ida >= ?"
        params.append(fecha_ida_desde)
    if fecha_ida_hasta:
        sql += " AND ida <= ?"
        params.append(fecha_ida_hasta)

    sql += " ORDER BY visto_en DESC, precio ASC LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/mejores-del-dia")
def mejores_del_dia(limit: int = 10):
    return ofertas(solo_gangas=True, limit=limit, horas=36)