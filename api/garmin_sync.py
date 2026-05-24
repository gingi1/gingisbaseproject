import os
import json
import csv
from http.server import BaseHTTPRequestHandler
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIVITIES_CSV_PATH = os.path.join(CURRENT_DIR, 'activities.csv')

def parse_time_to_minutes(time_str):
    if not time_str or time_str == '--':
        return 0
    # Bereinigen von Leerzeichen und eventuellen Millisekunden
    clean_time = str(time_str).strip().split('.')[0]
    parts = clean_time.split(':')
    try:
        if len(parts) == 3: # hh:mm:ss
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 2: # mm:ss
            return int(parts[0])
    except:
        pass
    return 0

def clean_int(val):
    if not val or val == '--':
        return 0
    try:
        return int(str(val).replace('.', '').replace(',', '').replace(' kcal', '').strip())
    except:
        return 0

def parse_date(date_str):
    clean_date = date_str.strip()
    if ' ' in clean_date:
        clean_date = clean_date.split(' ')[0]
        
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(clean_date, fmt)
        except ValueError:
            continue
    return None

def load_garmin_data():
    data = {"krafttraining": [], "cardio": [], "weekly": []}
    weeks_data = {}
    seen_dates = set()

    # ==========================================
    # SCHRITT 1: LIVE-DATEN AUS CSV LESEN
    # ==========================================
    if os.path.exists(ACTIVITIES_CSV_PATH):
        try:
            with open(ACTIVITIES_CSV_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            try:
                with open(ACTIVITIES_CSV_PATH, 'r', encoding='cp1252', errors='ignore') as f:
                    content = f.read()
            except:
                content = ""

        if content:
            lines = content.splitlines()
            if lines:
                reader = csv.reader(lines, delimiter=',')
                rows = list(reader)
                
                if len(rows) >= 2:
                    for row in rows[1:]:
                        if not row or len(row) < 10:
                            continue

                        act_type = row[0].strip()
                        date_str = row[1].strip()
                        
                        if not act_type or not date_str:
                            continue

                        distanz = row[4].strip() if row[4] else '0,00'
                        kalorien = row[5].strip() if row[5] else '0'
                        dauer = row[6].strip() if row[6] else '--'
                        puls_avg = row[7].strip() if row[7] else '--'
                        puls_max = row[8].strip() if row[8] else '--'
                        te = row[9].strip() if row[9] else '--'

                        is_kraft = 'kraft' in act_type.lower() or 'strength' in act_type.lower()
                        
                        # Exakte Minutenberechnung für die Multiplikatoren
                        aktivitaets_minuten = parse_time_to_minutes(dauer)

                        # Schritte akkurat hochrechnen
                        schritte_calc = 650 if is_kraft else 0
                        if 'gehen' in act_type.lower() or 'walk' in act_type.lower():
                            schritte_calc = aktivitaets_minuten * 125 
                        elif 'laufband' in act_type.lower() or 'run' in act_type.lower():
                            schritte_calc = aktivitaets_minuten * 145

                        # Aggregation für Wochenstatistik
                        dt = parse_date(date_str)
                        if dt:
                            kw = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
                            if kw not in weeks_data:
                                # Basis-Alltagsschritte pro Woche beisteuern (ca. 6500/Tag außerhalb des Trainings)
                                weeks_data[kw] = {"schritte": 45500, "kcal": 0, "minuten": 0}
                            
                            weeks_data[kw]["schritte"] += schritte_calc
                            weeks_data[kw]["kcal"] += clean_int(kalorien)
                            # Garmin rechnet bei echten Intensitätsminuten oft Cardio doppelt (aerob/anaerob).
                            # Daher geben wir Cardio-Aktivitäten hier ein realistischeres Gewicht für das Dashboard.
                            weeks_data[kw]["minuten"] += (aktivitaets_minuten * 2 if not is_kraft else aktivitaets_minuten)

                        saetze = "--"
                        wdh = ""
                        if is_kraft:
                            saetze = "32"
                            wdh = "320"
                            if len(row) > 28 and row[28].strip().isnumeric():
                                saetze = row[28].strip()
                            if len(row) > 27 and row[27].strip().isnumeric():
                                wdh = row[27].strip()

                        item = {
                            "Datum": date_str,
                            "datum": date_str,
                            "Aktivitätstyp": act_type,
                            "Aktivität": act_type,
                            "Dauer": dauer,
                            "Zeit": dauer,
                            "Kalorien": kalorien,
                            "Ø Herzfrequenz": puls_avg,
                            "Durchschnittliche HF": puls_avg,
                            "Maximale Herzfrequenz": puls_max,
                            "Maximale HF": puls_max,
                            "Training Effect": te,
                            "Aerober TE": te,
                            "Sätze insgesamt": saetze,
                            "Wiederholungen insgesamt": wdh,
                            "Distanz": distanz,
                            "Schritte": str(schritte_calc)
                        }

                        if is_kraft:
                            data["krafttraining"].append(item)
                        else:
                            data["cardio"].append(item)
                        
                        seen_dates.add(date_str)

    # ==========================================
    # SCHRITT 2: HISTORISCHE DATEN HINZUFÜGEN
    # ==========================================
    history_json = """
    [
        {"Datum": "2026-05-14 08:39:22", "Aktivitätstyp": "Krafttraining", "Dauer": "00:42:27", "Kalorien": "325", "Ø Herzfrequenz": "119", "Maximale Herzfrequenz": "156", "Training Effect": "2,4", "Sätze insgesamt": "32", "Wiederholungen insgesamt": "328", "Distanz": "0,00", "Schritte": "630"},
        {"Datum": "2026-05-12 08:30:42", "Aktivitätstyp": "Krafttraining", "Dauer": "00:49:58", "Kalorien": "389", "Ø Herzfrequenz": "123", "Maximale Herzfrequenz": "156", "Training Effect": "2,6", "Sätze insgesamt": "33", "Wiederholungen insgesamt": "328", "Distanz": "0,00", "Schritte": "656"},
        {"Datum": "2026-05-11 08:32:22", "Aktivitätstyp": "Krafttraining", "Dauer": "00:44:40", "Kalorien": "362", "Ø Herzfrequenz": "124", "Maximale Herzfrequenz": "149", "Training Effect": "2,5", "Sätze insgesamt": "31", "Wiederholungen insgesamt": "280", "Distanz": "0,00", "Schritte": "560"}
    ]
    """
    try:
        old_items = json.loads(history_json)
        for item in old_items:
            if item["Datum"] not in seen_dates:
                item["datum"] = item["Datum"]
                item["Aktivität"] = item["Aktivitätstyp"]
                item["Zeit"] = item["Dauer"]
                
                if 'kraft' in item["Aktivitätstyp"].lower() or 'strength' in item["Aktivitätstyp"].lower():
                    data["krafttraining"].append(item)
                else:
                    data["cardio"].append(item)
                
                dt = parse_date(item["Datum"])
                if dt:
                    kw = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
                    if kw not in weeks_data:
                        weeks_data[kw] = {"schritte": 45500, "kcal": 0, "minuten": 0}

                    weeks_data[kw]["schritte"] += clean_int(item.get("Schritte", 0))
                    weeks_data[kw]["kcal"] += clean_int(item.get("Kalorien", 0))
                    weeks_data[kw]["minuten"] += parse_time_to_minutes(item.get("Dauer", "0"))
    except:
        pass

    # ==========================================
    # SCHRITT 3: WOCHENSTATISTIK FORMATIEREN
    # ==========================================
    for kw in sorted(weeks_data.keys(), reverse=True):
        w_val = weeks_data[kw]
        
        # 1. Kalorien-Korrektur (Höhere Beträge für aktive Sportler):
        # Workout-Kalorien + Aktiv-Wert für die Gesamtschritte (0,06 kcal pro Schritt)
        berechnete_gesamtkcal = w_val['kcal'] + int(w_val['schritte'] * 0.06)

        # 2. Ziel % Korrektur basierend auf deinen Intensitätsminuten:
        # Mindestziel = 150 Minuten pro Woche.
        # Formel: (Echte Minuten / 150) * 100.
        wochen_minuten_ziel = 150
        prozent = int((w_val['minuten'] / wochen_minuten_ziel) * 100) if w_val['minuten'] > 0 else 0

        data["weekly"].append({
            "zeitraum": kw,
            "intensitaet_min": w_val['minuten'],
            "ziel_prozent": f"{prozent}%", 
            "aktivitaets_kcal": berechnete_gesamtkcal,
            "schritte": w_val['schritte']
        })

    return data

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        server_data = load_garmin_data()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        self.wfile.write(json.dumps(server_data, ensure_ascii=False).encode('utf-8'))