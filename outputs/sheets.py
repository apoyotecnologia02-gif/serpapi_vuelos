import os
from datetime import datetime
from zoneinfo import ZoneInfo
 
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
 
from config.settings import (SHEET_ID, CLIENT_SECRET_FILE, TOKEN_FILE, IATAS)
 
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
 
ENCABEZADOS = [
    "Fecha Carga", "Origen", "Destino", "Fecha Ida", "Fecha Regreso", "Noches",
    # veredicto primero: es lo que el asesor mira
    "Precio Total", "Veredicto", "% vs Piso", "Es Ganga", "Piso Tipico", "Techo Tipico",
    # vendedor
    "Vendedor", "Precio Vendedor", "Equipaje", "Tiquetes Separados",
    # ida
    "Aerolinea Ida", "Vuelo Ida", "Salida Ida", "Llegada Ida", "Escalas Ida", "Duracion Ida",
    # regreso
    "Aerolinea Regreso", "Vuelo Regreso", "Salida Regreso", "Llegada Regreso",
    "Escalas Regreso", "Duracion Regreso",
    "Moneda", "Link Google Flights",
]
 
_svc = None
_meta = {}
 
 
def _cred():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds
 
 
def servicio():
    global _svc
    if _svc is None:
        if not SHEET_ID:
            raise SystemExit("Falta SHEET_ID en el .env")
        _svc = build("sheets", "v4", credentials=_cred())
    return _svc
 
 
def _pesos(v):
    if v is None or v == "":
        return ""
    try:
        return f"$ {float(v):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return ""
 
 
def _txt(v):
    return f"'{v}" if v else ""
 
 
def _hoja_lista(hoja):
    """Crea la pestania si falta y garantiza encabezados. Cachea el sheetId."""
    s = servicio()
    if hoja not in _meta:
        libro = s.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        for h in libro["sheets"]:
            _meta[h["properties"]["title"]] = h["properties"]["sheetId"]
    if hoja not in _meta:
        r = s.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": hoja}}}]},
        ).execute()
        _meta[hoja] = r["replies"][0]["addSheet"]["properties"]["sheetId"]
        print(f"  [sheets] hoja '{hoja}' creada")
 
    fila1 = s.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{hoja}'!A1:AD1").execute().get("values", [[]])
    if not fila1 or fila1[0][:1] != [ENCABEZADOS[0]]:
        s.spreadsheets().values().update(
            spreadsheetId=SHEET_ID, range=f"'{hoja}'!A1",
            valueInputOption="RAW", body={"values": [ENCABEZADOS]},
        ).execute()
        _formato_ganga(hoja)
 
 
def _formato_ganga(hoja):
    """Verde claro en las filas donde 'Es Ganga' = Si. Se pone una sola vez."""
    col = ENCABEZADOS.index("Es Ganga")          # 0-based
    letra = chr(65 + col) if col < 26 else "A" + chr(65 + col - 26)
    try:
        servicio().spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": [{"sheetId": _meta[hoja], "startRowIndex": 1,
                            "startColumnIndex": 0, "endColumnIndex": len(ENCABEZADOS)}],
                "booleanRule": {
                    "condition": {"type": "CUSTOM_FORMULA",
                                  "values": [{"userEnteredValue": f'=${letra}2="Si"'}]},
                    "format": {"backgroundColor": {"red": .85, "green": .94, "blue": .83}},
                }}}}]},
        ).execute()
    except Exception as e:
        print(f"  [sheets] aviso: no se pudo poner el formato verde ({e})")
 
 
def _fila(o):
    return [
        datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M"),
        IATAS.get(o["origen"], o["origen"]),
        IATAS.get(o["destino"], o["destino"]),
        _txt(o["ida"]), _txt(o["regreso"]), o["noches"],
        _pesos(o["precio"]), o.get("veredicto", ""),
        o["pct_vs_piso"] if o.get("pct_vs_piso") is not None else "",
        "Si" if o.get("ganga") else "No",
        _pesos((o.get("rango") or [None, None])[0]),
        _pesos((o.get("rango") or [None, None])[1]),
        o.get("vendedor", ""), _pesos(o.get("precio_vendedor")),
        o.get("equipaje", ""), "Si" if o.get("separate_tickets") else "",
        o.get("aerolinea_ida", ""), o.get("vuelo_ida", ""),
        _txt(o.get("salida_ida")), _txt(o.get("llegada_ida")),
        o.get("escalas_ida", ""), o.get("duracion_ida", ""),
        o.get("aerolinea_regreso", ""), o.get("vuelo_regreso", ""),
        _txt(o.get("salida_regreso")), _txt(o.get("llegada_regreso")),
        o.get("escalas_regreso", ""), o.get("duracion_regreso", ""),
        o.get("moneda", "COP"), o.get("link", ""),
    ]
 
 
def escribir(oferta):
    """Inserta la oferta en la fila 2 (lo nuevo arriba, lo viejo baja)."""
    hoja = oferta.get("hoja") or IATAS.get(oferta["destino"], oferta["destino"])
    try:
        _hoja_lista(hoja)
        s = servicio()
        s.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"insertDimension": {
                "range": {"sheetId": _meta[hoja], "dimension": "ROWS",
                          "startIndex": 1, "endIndex": 2},
                "inheritFromBefore": False}}]},
        ).execute()
        s.spreadsheets().values().update(
            spreadsheetId=SHEET_ID, range=f"'{hoja}'!A2",
            valueInputOption="RAW", body={"values": [_fila(oferta)]},
        ).execute()
    except Exception as e:
        print(f"  [sheets] ERROR en '{hoja}': {type(e).__name__}: {e}")