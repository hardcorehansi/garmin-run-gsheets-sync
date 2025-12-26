import os
import json
from garminconnect import Garmin
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

def format_duration(seconds):
    return round(seconds / 60, 2) if seconds else 0

def format_sleep(seconds):
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
    print("🚀 Garmin 2 GDrive - Fokus: Aktivitäts-Gewicht...")
    
    garmin_email = os.environ.get('GARMIN_EMAIL')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')
    
    if not all([garmin_email, garmin_password, google_creds_json, sheet_id]):
        print("❌ Fehlende Umgebungsvariablen!")
        return
    
    try:
        garmin = Garmin(garmin_email, garmin_password)
        garmin.login()
        print("✅ Garmin Login erfolgreich")
    except Exception as e:
        print(f"❌ Garmin Login Fehler: {e}")
        return
    
    activities = garmin.get_activities(0, 15)

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
            
            # --- GEWICHT DIREKT AUS DER AKTIVITÄT ---
            # Wir suchen in den Metadaten der Aktivität nach dem Gewicht
            weight_raw = activity.get('userWeight', 0) # Standard-Feld in vielen Aktivitäts-JSONs
            
            # Falls nicht vorhanden, probieren wir das Feld in den 'summaries' (falls vorhanden)
            if not weight_raw:
                weight_raw = activity.get('weight', 0)

            # Umrechnung Gramm -> KG (Aktivitäts-Gewicht ist oft schon in KG, aber wir prüfen beides)
            if weight_raw > 1000:
                weight = round(weight_raw / 1000, 2)
            else:
                weight = round(weight_raw, 2)

            # --- RESTLICHE GESUNDHEITSDATEN ---
            rhr = 0
            hrv = 'N/A'
            sleep_hours = 0
            try:
                stats = garmin.get_stats(act_date)
                rhr = stats.get('restingHeartRate', 0)
                
                hrv_data = garmin.get_hrv_data(act_date)
                if hrv_data:
                    hrv = hrv_data.get('hrvSummary', {}).get('lastNightAvg', 'N/A')
                
                sleep_data = garmin.get_sleep_data(act_date)
                if sleep_data:
                    sleep_seconds = sleep_data.get('dailySleepDTO', {}).get('sleepTimeSeconds', 0)
                    sleep_hours = format_sleep(sleep_seconds)
            except:
                pass

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
                weight,                                     # K: Gewicht aus Aktivität
                rhr,                                        # L
                hrv,                                        # M
                sleep_hours                                 # N
            ]
            
            sheet.append_row(row)
            print(f"✅ Sync: {activity_name} (Gewicht: {weight}kg)")
            new_entries += 1
            
        except Exception as e:
            print(f"❌ Fehler bei Aktivität {start_time}: {e}")

    print(f"✨ Fertig! {new_entries} neue Einträge.")

if __name__ == "__main__":
    main()
