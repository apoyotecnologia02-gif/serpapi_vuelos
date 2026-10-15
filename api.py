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
    solo_gangas: bool = True,
    limit: int = Query(20, le=50),
    origen: str | None = None,
    destino: str | None = None,
    horas: int = 48,           # solo las de las últimas X horas
):
    con = get_db()
    corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()

    sql = """
        SELECT * FROM ofertas
        WHERE visto_en > ?
    """

    params = [corte]

    if solo_gangas:
        sql += " AND ganga = 1"
    if origen:
        sql += " AND origen = ?"
        params.append(origen.upper())
    if destino:
        sql += " AND destino = ?"
        params.append(destino.upper())

    sql += " ORDER BY precio ASC LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/mejores-del-dia")
def mejores_del_dia(limit: int = 10):
    return ofertas(solo_gangas=True, limit=limit, horas=36)