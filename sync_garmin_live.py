import os
import csv
from datetime import datetime, timedelta
from garminconnect import Garmin

# Holt sich die Zugangsdaten absolut sicher aus den GitHub-Geheimnissen
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(CURRENT_DIR, 'api', 'activities.csv')

def sync_live_data():
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        print("Fehler: Garmin Zugangsdaten fehlen in den Umgebungsvariablen!")
        return

    print("Starte Verbindung zu Garmin Connect...")
    try:
        client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
        client.login()
        print("Login erfolgreich!")

        today = datetime.now()
        start_date = today - timedelta(days=30)
        
        print(f"Hole Aktivitäten vom {start_date.strftime('%Y-%m-%d')} bis heute...")
        activities = client.get_activities_by_date(
            start_date.strftime("%Y-%m-%d"), 
            today.strftime("%Y-%m-%d")
        )
        
        if not activities:
            print("Keine neuen Aktivitäten im Zeitraum gefunden.")
            return

        # Bestehende CSV lesen
        existing_rows = []
        header = []
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, [])
                existing_rows = list(reader)

        if not header:
            header = ["Aktivitätstyp", "Datum", "Favorit", "Titel", "Distanz", "Kalorien", "Zeit", "Ø Herzfrequenz", "Maximale Herzfrequenz", "AerobTE"]

        seen_datestamps = {row[1].strip() for row in existing_rows if len(row) > 1}

        new_rows = []
        for act in activities:
            raw_date = act.get('startTimeLocal', '')
            if not raw_date or raw_date in seen_datestamps:
                continue

            act_type = act.get('activityType', {}).get('typeKey', 'Unbekannt')
            title = act.get('activityName', '')
            distanz = f"{act.get('distance', 0) / 1000:.2f}".replace('.', ',')
            kalorien = str(int(act.get('calories', 0)))
            
            duration_secs = int(act.get('duration', 0))
            h = duration_secs // 3600
            m = (duration_secs % 3600) // 60
            s = duration_secs % 60
            dauer_str = f"{h:02d}:{m:02d}:{s:02d}"

            puls_avg = str(int(act.get('averageHR', 0))) if act.get('averageHR') else '--'
            puls_max = str(int(act.get('maxHR', 0))) if act.get('maxHR') else '--'
            te = f"{act.get('aerobicTrainingEffect', 0):.1f}".replace('.', ',')

            row = [act_type, raw_date, "false", title, distanz, kalorien, dauer_str, puls_avg, puls_max, te]
            new_rows.append(row)

        if not new_rows:
            print("Alle Aktivitäten bereits vorhanden.")
            return

        print(f"Füge {len(new_rows)} neue Aktivitäten oben ein...")
        all_data = new_rows + existing_rows

        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(all_data)

        print("Synchronisation abgeschlossen!")

    except Exception as e:
        print(f"Fehler beim Live-Sync: {e}")

if __name__ == "__main__":
    sync_live_data()
