import sqlite3
import sys

COLUMNAS_NUEVAS = {
    "veredicto":         "TEXT",
    "vuelo_ida":         "TEXT",
    "salida_ida":        "TEXT",
    "llegada_ida":       "TEXT",
    "duracion_ida":      "TEXT",
    "vuelo_regreso":     "TEXT",
    "salida_regreso":    "TEXT",
    "llegada_regreso":   "TEXT",
    "duracion_regreso":  "TEXT",
    "equipaje":          "TEXT",
    "separate_tickets":  "INTEGER",
}

def main(ruta_db: str) -> int:
    print(f"DB: {ruta_db}")

    con = sqlite3.connect(ruta_db, isolation_level=None, timeout=30)

    try:
        con.execute("PRAGMA journal_mode=WAL")

        actuales = {r[1] for r in con.execute("PRAGMA table_info(ofertas)")}

        if not actuales:
            print("ERROR: la tabla 'ofertas' no existe en esta DB.", file=sys.stderr)
            return 1

        print(f"Columnas actuales: {len(actuales)}")

        faltantes = [c for c in COLUMNAS_NUEVAS if c not in actuales]
        if not faltantes:
            print("Nada que migrar: la DB ya tiene todas las columnas.")
            return 0

        print(f"Faltan {len(faltantes)} columnas: {faltantes}")

        con.execute("BEGIN IMMEDIATE")

        try:
            for nombre in faltantes:
                tipo = COLUMNAS_NUEVAS[nombre]
                con.execute(f"ALTER TABLE ofertas ADD COLUMN {nombre} {tipo}")
                print(f"  + {nombre} {tipo}")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            print("ERROR: rollback aplicado. La DB quedó como estaba.", file=sys.stderr)
            raise

        finales = {r[1] for r in con.execute("PRAGMA table_info(ofertas)")}
        siguen_faltando = [c for c in COLUMNAS_NUEVAS if c not in finales]

        if siguen_faltando:
            print(f"ERROR: siguen faltando {siguen_faltando}", file=sys.stderr)
            return 2

        print(f"\nOK. Columnas finales: {len(finales)}")
        print("Integridad:", con.execute("PRAGMA integrity_check").fetchone()[0])
        print("Filas en ofertas:", con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0])

        return 0
    finally:
        con.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 migrar_vuelos.py /ruta/a/vuelos.db", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(sys.argv[1]))