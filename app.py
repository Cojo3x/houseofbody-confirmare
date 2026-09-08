import os
import json
import re
import requests
from urllib.parse import quote
from flask import Flask, redirect, render_template_string
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)

# ==================================================================
# CONFIGURARE - toate valorile astea vin din variabile de mediu
# setate in Render (Environment tab), NU sunt scrise direct in cod.
# ==================================================================

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
CALENDAR_ID = os.environ.get("CALENDAR_ID", "primary")

SMTP2GO_API_KEY = os.environ.get("SMTP2GO_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL")

BASE_URL = "https://houseofbody.ro"


# ==================================================================
# ȘABLONUL VIZUAL ȘI SALVAREA CELOR 4 PAGINI ÎN VARIABILE
# ==================================================================

_SABLON_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status Programare</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f6f9;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }}
        .container {{
            text-align: center;
            background: white;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            max-width: 400px;
            width: 90%;
        }}
        .status-btn {{
            display: block;
            width: 100%;
            padding: 25px 20px;
            font-size: 18px;
            font-weight: bold;
            color: white;
            border: none;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
            text-decoration: none;
            line-height: 1.5;
            cursor: default;
            box-sizing: border-box;
        }}
        .btn-verde {{ background-color: #2ecc71; }}
        .btn-rosu {{ background-color: #e74c3c; }}
        
        .info-box {{
            display: block;
            background-color: #7f8c8d;
            color: white;
            padding: 14px 20px;
            font-size: 15px;
            border-radius: 8px;
            font-weight: bold;
            width: 100%;
            box-sizing: border-box;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="status-btn {clasa_buton}">
            {text_status}
        </div>
        <div class="info-box">
            Pentru a inchide fereasta apasa BACK pe telefon
        </div>
    </div>
</body>
</html>
"""

# Cele 4 pagini salvate curat în variabile globale dedesubt
PAGINA_DEJA_CONFIRMAT = _SABLON_HTML.format(
    clasa_buton="btn-verde", 
    text_status="Sedinta a fost deja confirmata."
)

PAGINA_CONFIRMARE_SUCCES = _SABLON_HTML.format(
    clasa_buton="btn-verde", 
    text_status="Multumim! Programarea ta a fost inregistrata ca si confirmata."
)

PAGINA_REPROGRAMARE_SUCCES = _SABLON_HTML.format(
    clasa_buton="btn-rosu", 
    text_status="Veti fi contactat pe WhatsApp cat mai curand posibil."
)

PAGINA_DEJA_REPROGRAMAT = _SABLON_HTML.format(
    clasa_buton="btn-rosu", 
    text_status="Sedinta a fost deja reprogramata."
)


# ==================================================================
# RUTA HOME: pagina goala (fara cod si telefon in link)
# ==================================================================

@app.route('/')
def home():
    return (
        "Acest link nu este complet. Foloseste link-ul primit prin "
        "WhatsApp sau email, care contine un cod de confirmare."
    )


# ==================================================================
# FUNCTII AJUTATOARE
# ==================================================================

def get_calendar_service():
    """Creeaza o conexiune autentificata catre Google Calendar API."""
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://googleapis.com"]
    )
    return build("calendar", "v3", credentials=credentials)


def sterge_trebuie_din_titlu(event):
    """Elimina cuvantul 'Trebuie' din titlul evenimentului."""
    titlu_vechi = event.get("summary", "")
    titlu_nou = re.sub(r"trebuie\s?", "", titlu_vechi, flags=re.IGNORECASE)
    titlu_nou = re.sub(r"\s{2,}", " ", titlu_nou)
    titlu_nou = titlu_nou.strip()
    titlu_nou = titlu_nou.lstrip("-").strip()
    return titlu_nou


def extrage_nume_din_titlu(event):
    """Extrage numele clientului din primele doua cuvinte ale titlului."""
    titlu = event.get("summary", "")
    cuvinte = titlu.split()
    return " ".join(cuvinte[:2]) if cuvinte else "client"


def extrage_ora_eveniment(event):
    """Extrage ora de inceput a evenimentului, in format HH:MM."""
    from datetime import datetime

    start = event.get("start", {})
    data_ora = start.get("dateTime")

    if not data_ora:
        return "(toata ziua)"

    dt = datetime.fromisoformat(data_ora)
    return dt.strftime("%H:%M")


def verifica_si_actualizeaza_reprogramare(service, cod, event):
    """Verifica ziua evenimentului și îl mută sau îl șterge."""
    from datetime import datetime, timedelta

    start = event.get("start", {})
    end = event.get("end", {})

    are_ora = "dateTime" in start

    if are_ora:
        start_dt = datetime.fromisoformat(start["dateTime"])
        ziua_saptamanii = start_dt.weekday()
    else:
        start_date = datetime.fromisoformat(start["date"]).date()
        ziua_saptamanii = start_date.weekday()

    if ziua_saptamanii == 4:  # Vineri
        service.events().delete(calendarId=CALENDAR_ID, eventId=cod).execute()
        return "sters"

    if are_ora:
        event["start"]["dateTime"] = (start_dt + timedelta(days=1)).isoformat()
    else:
        event["start"]["date"] = (start_date + timedelta(days=1)).isoformat()

    if "dateTime" in end:
        end_dt = datetime.fromisoformat(end["dateTime"])
        event["end"]["dateTime"] = (end_dt + timedelta(days=1)).isoformat()
    elif "date" in end:
        end_date = datetime.fromisoformat(end["date"]).date()
        event["end"]["date"] = (end_date + timedelta(days=1)).isoformat()

    data_noua = event["start"]["dateTime"] if are_ora else event["start"]["date"]
    event.setdefault("extendedProperties", {}).setdefault("private", {})
    event["extendedProperties"]["private"]["reprogramat_pentru"] = data_noua

    service.events().update(calendarId=CALENDAR_ID, eventId=cod, body=event).execute()
    return "mutat"


def trimite_email(destinatar, subiect, continut):
    """Trimite un email prin SMTP2GO API."""
    url = "https://smtp2go.com"
    headers = {
        "Content-Type": "application/json",
        "X-Smtp2go-Api-Key": SMTP2GO_API_KEY,
        "Accept": "application/json"
    }
    payload = {
        "sender": SENDER_EMAIL,
        "to": [destinatar],
        "subject": subject,
        "text_body": continut
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    data = response.json() if response.headers.get("Content-Type", "").startswith("application/json") else {}
    esuat = data.get("data", {}).get("failed", 0)

    if response.status_code >= 300 or esuat:
        raise Exception(f"SMTP2GO a raspuns cu eroare: {response.text}")


# ==================================================================
# RUTA 1: Clientul confirma programarea
# ==================================================================

@app.route('/<cod>/<telefon>')
def confirmare_client(cod, telefon):

    try:
        service = get_calendar_service()
        event = service.events().get(calendarId=CALENDAR_ID, eventId=cod).execute()
    except Exception as e:
        return f"A aparut o eroare la citirea programarii din calendar: {e}", 500

    titlu_curent = event.get("summary", "")
    deja_confirmat = "trebuie" not in titlu_curent.lower()

    if deja_confirmat:
        return PAGINA_DEJA_CONFIRMAT

    try:
        nume = extrage_nume_din_titlu(event)
        ora = extrage_ora_eveniment(event)

        event["summary"] = sterge_trebuie_din_titlu(event)

        service.events().update(
            calendarId=CALENDAR_ID, eventId=cod, body=event
        ).execute()

    except Exception as e:
        return f"A aparut o eroare la actualizarea programarii in calendar: {e}", 500

    link_owner = f"{BASE_URL}/owner/{cod}/{telefon}"

    try:
        trimite_email(
            OWNER_EMAIL,
            f"{nume} a confirmat sedinta de {ora}",
            f"Apasa aici pentru a trimite confirmarea finala catre client pe WhatsApp:\n"
            f"{link_owner}"
        )
    except Exception as e:
        return (
            "Programarea a fost inregistrata in calendar, dar notificarea prin "
            f"email a esuat: {e}"
        ), 500

    return PAGINA_CONFIRMARE_SUCCES


# ==================================================================
# RUTA 2: Tu confirmi programarea (Redirecționare automată)
# ==================================================================

@app.route('/owner/<cod>/<telefon>')
def confirmare_owner(cod, telefon):
    mesaj = (
        "Buna! Programarea dumneavoastra a fost confirmata de echipa noastra. "
        "Va asteptam!"
    )
    link_whatsapp = f"https://wa.me{telefon}?text={quote(mesaj)}"
    return redirect(link_whatsapp)


# ==================================================================
# RUTA 3: Clientul cere reprogramare
