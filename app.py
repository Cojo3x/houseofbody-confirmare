import os
import json
import smtplib
from email.mime.text import MIMEText
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

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
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
    """Elimina cuvantul 'Trebuie' din titlul evenimentului, curatand
    si eventualele spatii sau liniute ramase in urma stergerii."""
    titlu_vechi = event.get("summary", "")
    titlu_nou = titlu_vechi.replace("Trebuie ", "")
    titlu_nou = titlu_nou.strip()
    titlu_nou = titlu_nou.lstrip("-").strip()
    return titlu_nou


def trimite_email(destinatar, subiect, continut):
    """Trimite un email simplu prin Yahoo SMTP (gratuit)."""
    msg = MIMEText(continut)
    msg["Subject"] = subiect
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = destinatar

    with smtplib.SMTP_SSL("smtp.mail.yahoo.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, destinatar, msg.as_string())


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
        "Programarea dumneavoastra a fost confirmata de echipa noastra. "
        "Va asteptam!"
    )

    link_whatsapp = f"https://wa.me/{telefon}?text={quote(mesaj)}"
    return redirect(link_whatsapp)


if __name__ == '__main__':
    app.run()
