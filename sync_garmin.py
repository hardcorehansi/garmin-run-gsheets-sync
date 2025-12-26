import os
import json
from garminconnect import Garmin
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

def format_duration(seconds):
    return round(seconds / 60, 2) if seconds else 0

def format_sleep(seconds):
    # Wandelt Schlaf-Sekunden in Stunden um (z.B. 7.5 für 7 Std 30 Min)
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
    print("Starte High-End Garmin Sync (Final Version)...")
    
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
    
    # Aktivitäten abrufen
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

            # --- GESUNDHEITSDATEN SEKTION ---
            weight = 0
            rhr = 0
            hrv = 'N/A'
            sleep_hours = 0

            try:
                # 1. Ruhepuls
                stats = garmin.get_stats(act_date)
                rhr = stats.get('restingHeartRate', 0)
                
                # 2. Gewicht (Mehrstufige Abfrage)
                body_data = garmin.get_body_composition(act_date)
                weight_raw = None
                
                if body_data:
                    # Checke Liste (Standard-API) oder Direkt-Feld
                    if 'bodyCompositionList' in body_data and body_data['bodyCompositionList']:
                        weight_raw = body_data['bodyCompositionList'][0].get('weight')
                    else:
                        weight_raw = body_data.get('totalWeight') or body_data.get('weight')

                # Fallback: Wenn kein Gewicht für den Tag, nimm das letzte aus dem Profil
                if not weight_raw:
                    profile = garmin.get_user_profile()
                    weight_raw = profile.get('weight', 0)

                if weight_raw:
                    weight = round(weight_raw / 1000, 2) if weight_raw > 1000 else round(weight_raw, 2)
                
                # 3. HRV (Herzfrequenzvariabilität)
                hrv_data = garmin.get_hrv_data(act_date)
                if hrv_data:
                    hrv = hrv_data.get('hrvSummary', {}).get('lastNightAvg', 'N/A')
                
                # 4. Schlafzeit
                sleep_data = garmin.get_sleep_data(act_date)
                if sleep_data:
                    sleep_seconds = sleep_data.get('dailySleepDTO', {}).get('sleepTimeSeconds', 0)
                    sleep_hours = format_sleep(sleep_seconds)

            except Exception as health_e:
                print(f"⚠️ Hinweis: Teilweise Gesundheitsdaten für {act_date} nicht verfügbar.")

            # --- AKTIVITÄTSDATEN SEKTION ---
            dist_m = activity.get('distance', 0)
            dur_s = activity.get('duration', 0)
            dist_km = round(dist_m / 1000, 2)
            pace, kmh = calculate_speed_and_pace(dist_m, dur_s)
            
            row = [
                start_time,                                 # A
                activity_name,                              # B
                activity.get('activityType', {}).get('typeKey', 'n/a'), # C
                dist_km,                                    # D
                format_duration(dur_s),                      # E
                pace,                                       # F
                kmh,                                        # G
                activity.get('averageHR', 0),               # H
                activity.get('calories', 0),                # I
                round(activity.get('elevationGain', 0), 0), # J
                weight,                                     # K
                rhr,                                        # L
                hrv,                                        # M
                sleep_hours                                 # N
            ]
            
            sheet.append_row(row)
            print(f"✅ Sync Erfolg: {start_time} | {activity_name} (Gewicht: {weight}kg, Schlaf: {sleep_hours}h)")
            new_entries += 1
            
        except Exception as e:
            print(f"❌ Kritischer Fehler bei Aktivität {start_time}: {e}")

    print(f"🚀 Fertig! {new_entries} neue Einträge hinzugefügt.")

if __name__ == "__main__":
    main()
