import os
import json
from garminconnect import Garmin
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

def format_duration(seconds):
    """Konvertiert Sekunden in Minuten (auf 2 Dezimalstellen)"""
    return round(seconds / 60, 2) if seconds else 0

def calculate_speed_and_pace(distance_meters, duration_seconds):
    """Berechnet Pace (min/km) und Geschwindigkeit (km/h)"""
    if not distance_meters or not duration_seconds:
        return "0:00", 0
    
    distance_km = distance_meters / 1000
    # km/h Berechnung
    speed_kmh = round((distance_km / (duration_seconds / 3600)), 2)
    
    # Pace Berechnung (min/km)
    pace_decimal = (duration_seconds / 60) / distance_km
    pace_min = int(pace_decimal)
    pace_sec = int((pace_decimal - pace_min) * 60)
    pace_str = f"{pace_min}:{pace_sec:02d}"
    
    return pace_str, speed_kmh

def main():
    print("Starte Garmin Sync für ALLE Aktivitäten...")
    
    # Credentials laden
    garmin_email = os.environ.get('GARMIN_EMAIL')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')
    
    if not all([garmin_email, garmin_password, google_creds_json, sheet_id]):
        print("❌ Fehlende Umgebungsvariablen")
        return
    
    # 1. Garmin Verbindung
    try:
        garmin = Garmin(garmin_email, garmin_password)
        garmin.login()
        print("✅ Garmin verbunden")
    except Exception as e:
        print(f"❌ Garmin Fehler: {e}")
        return
    
    # 2. Aktivitäten abrufen (Kein Filter!)
    try:
        activities = garmin.get_activities(0, 20) 
        print(f"Gefunden: {len(activities)} Aktivitäten")
    except Exception as e:
        print(f"❌ Fehler beim Abrufen: {e}")
        return
    
    # 3. Google Sheets Verbindung
    try:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        )
        client = gspread.authorize(creds)
        # Öffnet die Tabelle direkt per ID aus den Secrets
        sheet = client.open_by_key(sheet_id).sheet1
        print("✅ Google Sheets verbunden")
    except Exception as e:
        print(f"❌ Google Sheets Fehler: {e}")
        return

    # Duplikatschutz: Vorhandene IDs (Datum + Zeit) laden
    existing_data = sheet.get_all_values()
    # Wir kombinieren Startzeit und Name als eindeutige ID
    existing_ids = [row[0] + row[1] for row in existing_data[1:]] if len(existing_data) > 1 else []

    new_entries = 0
    for activity in activities:
        try:
            start_time = activity.get('startTimeLocal', '')
            activity_name = activity.get('activityName', 'Aktivität')
            
            # Überspringen, falls schon vorhanden
            if start_time + activity_name in existing_ids:
                continue

            # Metriken extrahieren
            dist_m = activity.get('distance', 0)
            dur_s = activity.get('duration', 0)
            dist_km = round(dist_m / 1000, 2)
            
            pace, kmh = calculate_speed_and_pace(dist_m, dur_s)
            
            avg_hr = activity.get('averageHR', 0) or 0
            max_hr = activity.get('maxHR', 0) or 0
            calories = activity.get('calories', 0) or 0
            elevation = round(activity.get('elevationGain', 0), 1) if activity.get('elevationGain') else 0
            act_type = activity.get('activityType', {}).get('typeKey', 'n/a')
            
            # Neue Zeilenstruktur (Passend zu deiner Anforderung)
            row = [
                start_time,    # A: Datum/Zeit
                activity_name, # B: Name
                act_type,      # C: Typ
                dist_km,       # D: Distanz
                format_duration(dur_s), # E: Dauer
                pace,          # F: Pace
                kmh,           # G: km/h
                avg_hr,        # H: Puls Avg
                max_hr,        # I: Puls Max
                calories,      # J: Kalorien
                elevation      # K: Höhenmeter
            ]
            
            sheet.append_row(row)
            print(f"✅ Hinzugefügt: {start_time} - {act_type}")
            new_entries += 1
            
        except Exception as e:
            print(f"❌ Fehler bei Aktivität: {e}")

    print(f"\n🎉 Fertig! {new_entries} neue Einträge hinzugefügt.")

if __name__ == "__main__":
    main()
