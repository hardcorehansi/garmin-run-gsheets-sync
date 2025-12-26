import os
import json
from garminconnect import Garmin
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

def format_duration(seconds):
    return round(seconds / 60, 2) if seconds else 0

def format_sleep(seconds):
    # Wandelt Schlaf-Sekunden in Stunden um (z.B. 8.0 für 8 Stunden)
    return round(seconds / 3600, 2) if seconds else 0

def calculate_speed_and_pace(distance_meters, duration_seconds):
    if not distance_meters or not duration_seconds:
        return "0:00", 0
    distance_km = distance_meters / 1000
    speed_kmh = round((distance_km / (duration_seconds / 3600)), 2)
    pace_decimal = (duration_seconds / 60) / distance_km
    pace_min = int(pace_decimal)
    pace_sec = int((pace_decimal - pace_min) * 60)
    return f"{pace_min}:{pace_sec:02d}", speed_kmh

def main():
    print("Starte High-End Garmin Sync (inkl. Sleep Data)...")
    
    # Umgebungsvariablen laden
    garmin_email = os.environ.get('GARMIN_EMAIL')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')
    
    if not all([garmin_email, garmin_password, google_creds_json, sheet_id]):
        print("❌ Fehlende Umgebungsvariablen")
        return
    
    try:
        garmin = Garmin(garmin_email, garmin_password)
        garmin.login()
        print("✅ Garmin verbunden")
    except Exception as e:
        print(f"❌ Garmin Login Fehler: {e}")
        return
    
    # Letzte 15 Aktivitäten abrufen
    activities = garmin.get_activities(0, 15)

    # Google Sheets Verbindung
    try:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        print("✅ Google Sheets verbunden")
    except Exception as e:
        print(f"❌ Google Sheets Fehler: {e}")
        return

    existing_data = sheet.get_all_values()
    existing_ids = [row[0] + row[1] for row in existing_data[1:]] if len(existing_data) > 1 else []

    new_entries = 0
    for activity in activities:
        try:
            start_time = activity.get('startTimeLocal', '')
            activity_name = activity.get('activityName', 'Aktivität')
            
            if start_time + activity_name in existing_ids:
                continue

            act_date = start_time[:10]

            # Gesundheitsdaten abrufen
            try:
                stats = garmin.get_stats(act_date)
                rhr = stats.get('restingHeartRate', 0)
                
                # Letztes verfügbares Gewicht
                body_composition = garmin.get_body_composition() 
                weight = 0
                if body_composition:
                    weight_raw = body_composition.get('totalWeight') or body_composition.get('weight') or 0
                    if weight_raw > 1000:
                        weight = round(weight_raw / 1000, 2)
                    else:
                        weight = round(weight_raw, 2)
                
                # HRV Daten
                hrv_data = garmin.get_hrv_data(act_date)
                hrv = hrv_data.get('hrvSummary', {}).get('lastNightAvg', 'N/A') if hrv_data else 'N/A'
                
                # NEU: Schlafdaten abrufen
                sleep_data = garmin.get_sleep_data(act_date)
                sleep_seconds = sleep_data.get('dailySleepDTO', {}).get('sleepTimeSeconds', 0) if sleep_data else 0
                sleep_hours = format_sleep(sleep_seconds)

            except Exception as health_e:
                print(f"⚠️ Hinweis: Gesundheitsdaten unvollständig für {act_date}: {health_e}")
                weight, rhr, hrv, sleep_hours = 0, 0, 'N/A', 0

            dist_m = activity.get('distance', 0)
            dur_s = activity.get('duration', 0)
            dist_km = round(dist_m / 1000, 2)
            pace, kmh = calculate_speed_and_pace(dist_m, dur_s)
            
            # Zeilenstruktur für Google Sheets
            row = [
                start_time,                                 # A: Datum
                activity_name,                              # B: Name
                activity.get('activityType', {}).get('typeKey', 'n/a'), # C: Typ
                dist_km,                                    # D: km
                format_duration(dur_s),                      # E: Min
                pace,                                       # F: Pace
                kmh,                                        # G: km/h
                activity.get('averageHR', 0),               # H: HF Avg
                activity.get('calories', 0),                # I: kcal
                round(activity.get('elevationGain', 0), 0), # J: HM (Höhenmeter)
                weight,                                     # K: Gewicht
                rhr,                                        # L: RHR (Ruhepuls)
                hrv,                                        # M: HRV (HFV)
                sleep_hours                                 # N: Sleeptime (Std)
            ]
            
            sheet.append_row(row)
            print(f"✅ Sync Erfolg: {start_time} | {activity_name} (Schlaf: {sleep_hours}h)")
            new_entries += 1
            
        except Exception as e:
            print(f"❌ Fehler bei Aktivität {start_time}: {e}")

    print(f"🚀 Fertig! {new_entries} neue Einträge hinzugefügt.")

if __name__ == "__main__":
    main()
