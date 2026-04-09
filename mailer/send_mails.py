"""
Cold-Outreach Mailer — Sendet personalisierte E-Mails an Leads aus der CSV.
Nutzung: python send_mails.py [--test deine@email.de] [--dry-run] [--limit 5]
"""

import csv
import smtplib
import time
import argparse
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Config importieren
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

LEADS_PATH = os.path.join(os.path.dirname(__file__), "..", "leads", "leads.csv")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "mail_template.txt")


def load_template():
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    # Erste Zeile ist der Betreff
    lines = content.split("\n")
    betreff = lines[0].replace("Betreff: ", "")
    body = "\n".join(lines[2:])  # Ab Zeile 3 (nach Leerzeile)
    return betreff, body


def personalize(text, lead):
    replacements = {
        "{{FIRMENNAME}}": lead["firma"],
        "{{WEBSITE}}": lead["website"],
        "{{VORSCHAU_URL}}": lead["vorschau_url"],
        "{{DEIN_NAME}}": config.DEIN_NAME,
        "{{DEINE_EMAIL}}": config.DEINE_EMAIL,
        "{{DEINE_TELEFON}}": config.DEINE_TELEFON,
        "{{DEINE_STADT}}": config.DEINE_STADT,
        "{{IMPRESSUM}}": config.IMPRESSUM,
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def load_leads():
    leads = []
    with open(LEADS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)
    return leads


def save_leads(leads):
    if not leads:
        return
    fieldnames = leads[0].keys()
    with open(LEADS_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)


def send_email(smtp, sender, recipient, subject, body):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{config.DEIN_NAME} <{sender}>"
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    smtp.send_message(msg)


def main():
    parser = argparse.ArgumentParser(description="Cold-Outreach Mailer")
    parser.add_argument("--test", help="Testmail an diese Adresse senden (statt an Leads)")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nicht senden")
    parser.add_argument("--limit", type=int, default=config.MAILS_PRO_TAG,
                        help=f"Anzahl Mails (Standard: {config.MAILS_PRO_TAG})")
    args = parser.parse_args()

    betreff_template, body_template = load_template()
    leads = load_leads()

    # Leads filtern: nur Status "vorschau_erstellt"
    pending = [l for l in leads if l["status"] == "vorschau_erstellt"]

    if not pending and not args.test:
        print("Keine Leads mit Status 'vorschau_erstellt' gefunden.")
        print(f"Insgesamt {len(leads)} Leads in der CSV.")
        status_counts = {}
        for l in leads:
            s = l["status"]
            status_counts[s] = status_counts.get(s, 0) + 1
        for s, count in status_counts.items():
            print(f"  - {s}: {count}")
        return

    to_send = pending[:args.limit]

    # Test-Modus: eine Mail an die Testadresse
    if args.test:
        test_lead = {
            "firma": "Testfirma GmbH",
            "website": "www.testfirma.de",
            "email": args.test,
            "vorschau_url": f"{config.PREVIEW_BASE_URL}/testfirma-musterstadt/",
        }
        betreff = personalize(betreff_template, test_lead)
        body = personalize(body_template, test_lead)

        if args.dry_run:
            print(f"[DRY-RUN] An: {args.test}")
            print(f"Betreff: {betreff}")
            print(f"\n{body}")
            return

        print(f"Sende Testmail an {args.test}...")
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            send_email(smtp, config.SMTP_USER, args.test, betreff, body)
        print("Testmail gesendet!")
        return

    # Normaler Versand
    print(f"Starte Versand: {len(to_send)} von {len(pending)} ausstehenden Leads")
    print("-" * 50)

    if args.dry_run:
        for lead in to_send:
            betreff = personalize(betreff_template, lead)
            print(f"[DRY-RUN] {lead['firma']} -> {lead['email']}")
            print(f"  Betreff: {betreff}")
            print(f"  Vorschau: {lead['vorschau_url']}")
            print()
        return

    sent_count = 0
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)

        for i, lead in enumerate(to_send):
            betreff = personalize(betreff_template, lead)
            body = personalize(body_template, lead)

            try:
                send_email(smtp, config.SMTP_USER, lead["email"], betreff, body)
                lead["status"] = "gesendet"
                lead["gesendet_am"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                sent_count += 1
                print(f"[{sent_count}/{len(to_send)}] Gesendet: {lead['firma']} ({lead['email']})")
            except Exception as e:
                print(f"[FEHLER] {lead['firma']} ({lead['email']}): {e}")

            # Pause zwischen Mails (nicht nach der letzten)
            if i < len(to_send) - 1:
                print(f"  Warte {config.PAUSE_ZWISCHEN_MAILS_SEKUNDEN}s...")
                time.sleep(config.PAUSE_ZWISCHEN_MAILS_SEKUNDEN)

    # CSV aktualisieren
    save_leads(leads)
    print("-" * 50)
    print(f"Fertig! {sent_count} Mails gesendet. CSV aktualisiert.")


if __name__ == "__main__":
    main()
