import os
import json
import re
import requests
from urllib.parse import quote
from flask import Flask, redirect
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

BASE_URL = "https://confirmare.houseofbody.ro"


# ==================================================================
# CELE 4 PAGINI SALVATE ÎN VARIABILE CU GREEN/RED ȘI TEXTUL GRI
# ==================================================================

# 🟢 PAGINA 1: Deja confirmată (Buton Verde)
PAGINA_DEJA_CONFIRMAT = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status Programare</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 400px; width: 90%; }
        .status-btn { display: block; width: 100%; padding: 25px 20px; font-size: 18px; font-weight: bold; color: white; border: none; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); line-height: 1.5; background-color: #2ecc71; box-sizing: border-box; }
        .info-box { display: block; background-color: #7f8c8d; color: white; padding: 14px 20px; font-size: 15px; border-radius: 8px; font-weight: bold; width: 100%; box-sizing: border-box; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-btn">Sedinta a fost deja confirmata.</div>
        <div class="info-box">Pentru a inchide fereasta apasa BACK pe telefon</div>
    </div>
</body>
</html>
"""

# 🟢 PAGINA 2: Înregistrare cu succes (Buton Verde)
PAGINA_CONFIRMARE_SUCCES = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status Programare</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 400px; width: 90%; }
        .status-btn { display: block; width: 100%; padding: 25px 20px; font-size: 18px; font-weight: bold; color: white; border: none; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); line-height: 1.5; background-color: #2ecc71; box-sizing: border-box; }
        .info-box { display: block; background-color: #7f8c8d; color: white; padding: 14px 20px; font-size: 15px; border-radius: 8px; font-weight: bold; width: 100%; box-sizing: border-box; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-btn">Multumim! Programarea ta a fost inregistrata ca si confirmata.</div>
        <div class="info-box">Pentru a inchide fereasta apasa BACK pe telefon</div>
    </div>
</body>
</html>
"""

# 🔴 PAGINA 3: Cerere de reprogramare trimisă (Buton Roșu)
PAGINA_REPROGRAMARE_SUCCES = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status Programare</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 400px; width: 90%; }
        .status-btn { display: block; width: 100%; padding: 25px 20px; font-size: 18px; font-weight: bold; color: white; border: none; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); line-height: 1.5; background-color: #e74c3c; box-sizing: border-box; }
        .info-box { display: block; background-color: #7f8c8d; color: white; padding: 14px 20px; font-size: 15px; border-radius: 8px; font-weight: bold; width: 100%; box-sizing: border-box; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-btn">Veti fi contactat pe WhatsApp cat mai curand posibil.</div>
        <div class="info-box">Pentru a inchide fereasta apasa BACK pe telefon</div>
    </div>
</body>
</html>
"""

# 🔴 PAGINA 4: Deja reprogramată (Buton Roșu)
PAGINA_DEJA_REPROGRAMAT = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status Programare</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 400px; width: 90%; }
        .status-btn { display: block; width: 100%; padding: 25px 20px; font-size: 18px; font-weight: bold; color: white; border: none; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); line-height: 1.5; background-color: #e74c3c; box-sizing: border-box; }
        .info-box { display: block; background-color: #7f8c8d; color: white; padding: 14px 20px; font-size: 15px; border-radius: 8px; font-weight: bold; width: 100%; box-sizing: border-box; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-btn">Sedinta a fost deja reprogramata.</div>
        <div class="info-box">Pentru a inchide fereasta apasa BACK pe telefon</div>
    </div>
</body>
</html>
"""


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
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=credentials)


def sterge_trebuie_din_titlu(event):
    """Elimina cuvantul 'Trebuie' (si spatiul de dupa el, daca exista)
    din titlul evenimentului, indiferent de majuscule/minuscule."""
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
    url = "https://api.smtp2go.com/v3/email/send"
    headers = {
