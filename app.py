import os
import json
import re
import requests
from datetime import datetime
from urllib.parse import quote
from flask import Flask, redirect
from google.oauth2 import service_account
from googleapiclient.discovery import build

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
    din titlul evenimentului, indiferent de majuscule/minuscule
    (Trebuie, trebuie, TREBUIE etc.), curatand si eventualele spatii
    duble sau liniute ramase in urma stergerii."""
    titlu_vechi = event.get("summary", "")
    titlu_nou = re.sub(r"trebuie\s?", "", titlu_vechi, flags=re.IGNORECASE)
    titlu_nou = re.sub(r"\s{2,}", " ", titlu_nou)  # curata spatii duble ramase
    titlu_nou = titlu_nou.strip()
    titlu_nou = titlu_nou.lstrip("-").strip()
    return titlu_nou


def extrage_nume_client(event):
    """Extrage numele clientului din titlul evenimentului, presupunand
    formatul 'Nume Prenume <tip serviciu> trebuie confirmat'. Numele
    este format mereu din exact 2 cuvinte, primele din titlu."""
    titlu = event.get("summary", "")
    cuvinte = titlu.split()
    nume = " ".join(cuvinte[:2]) if len(cuvinte) >= 2 else titlu
    return nume.title()


def obtine_ora_start(event):
    """Extrage ora de start a evenimentului din Google Calendar si o
    formateaza ca HH:MM. Daca evenimentul e 'toata ziua' (fara ora
    exacta), returneaza un text alternativ."""
    start = event.get("start", {})
    dt_str = start.get("dateTime")

    if not dt_str:
        return "toata ziua"

    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%H:%M")


def trimite_email(destinatar, subiect, continut):
    """Trimite un email prin SMTP2GO API (HTTPS, port 443 - nu e blocat
    de host-uri gratuite, spre deosebire de SMTP)."""
    url = "https://api.smtp2go.com/v3/email/send"
    headers = {
        "Content-Type": "application/json",
        "X-Smtp2go-Api-Key": SMTP2GO_API_KEY,
        "Accept": "application/json"
    }
    payload = {
        "sender": SENDER_EMAIL,
        "to": [destinatar],
        "subject": subiect,
        "text_body": continut
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    data = response.json() if response.headers.get("Content-Type", "").startswith("application/json") else {}
    esuat = data.get("data", {}).get("failed", 0)

    if response.status_code >= 300 or esuat:
        raise Exception(f"SMTP2GO a raspuns cu eroare: {response.text}")


# ==================================================================
# RUTA 1: Clientul confirma programarea
# Link primit prin WhatsApp: confirmare.houseofbody.ro/<cod>/<telefon>
# ==================================================================

@app.route('/<cod>/<telefon>')
def confirmare_client(cod, telefon):

    # --- Pasul 1: actualizeaza evenimentul in Google Calendar ---
    try:
        service = get_calendar_service()
        event = service.events().get(calendarId=CALENDAR_ID, eventId=cod).execute()

        nume_client = extrage_nume_client(event)
        ora_start = obtine_ora_start(event)

        event["summary"] = sterge_trebuie_din_titlu(event)

        service.events().update(
            calendarId=CALENDAR_ID, eventId=cod, body=event
        ).execute()

    except Exception as e:
        return f"A aparut o eroare la actualizarea programarii in calendar: {e}", 500

    # --- Pasul 2: trimite-ti un EMAIL automat cu link de confirmare finala ---
    link_owner = f"{BASE_URL}/owner/{cod}/{telefon}"

    try:
        trimite_email(
            OWNER_EMAIL,
            "{nume_client} a confirmat sedinta de la ora {ora_start}",
            f"Apasa aici pentru a trimite confirmarea finala catre client pe WhatsApp:\n"
            f"{link_owner}"
        )
    except Exception as e:
        return (
            "Programarea a fost inregistrata in calendar, dar notificarea prin "
            f"email a esuat: {e}"
        ), 500

    return "Multumim! Programarea ta a fost inregistrata ca si confirmata."


# ==================================================================
# RUTA 2: Tu confirmi programarea (dupa ce ai primit email-ul)
# Link primit prin email: confirmare.houseofbody.ro/owner/<cod>/<telefon>
# La accesare, redirectioneaza automat catre WhatsApp cu mesajul gata scris.
# ==================================================================

@app.route('/owner/<cod>/<telefon>')
def confirmare_owner(cod, telefon):

    mesaj = (
        "Buna! Programarea dumneavoastra a fost confirmata de echipa noastra. "
        "Va asteptam!"
    )

    link_whatsapp = f"https://wa.me/{telefon}?text={quote(mesaj)}"
    return redirect(link_whatsapp)


if __name__ == '__main__':
    app.run()
