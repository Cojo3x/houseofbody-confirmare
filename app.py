import os
import json
import re
import requests
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

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
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


def trimite_email(destinatar, subiect, continut):
    """Trimite un email prin Brevo API (HTTPS, port 443 - nu e blocat
    de host-uri gratuite, spre deosebire de SMTP)."""
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "sender": {"email": SENDER_EMAIL},
        "to": [{"email": destinatar}],
        "subject": subiect,
        "textContent": continut
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    if response.status_code >= 300:
        raise Exception(f"Brevo a raspuns cu eroare {response.status_code}: {response.text}")


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
            "Client nou confirmat - programare",
            f"Un client a confirmat programarea (cod {cod}).\n\n"
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
