import os
import json
from garminconnect import Garmin
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime, timedelta
import time

def format_duration(seconds):
    return round(seconds / 60, 2) if seconds else 0

def format_sleep(seconds):
    return round(seconds / 3600, 2) if seconds else 0

def calculate_speed_and_pace(distance_meters, duration_seconds):
    if not distance_meters or not duration_seconds:
        return "0:00", 0
    distance_km = distance_meters / 1000
    speed_kmh = round((distance_km / (duration_seconds / 3600)), 2)
    pace_decimal = (duration_seconds / 60) / distance_km if distance_km > 0 else 0
    pace_min = int(pace_decimal)
    pace_sec = int((pace_decimal - pace_min) * 60)
    return f"{pace_min}:{pace_sec:02d}", speed_kmh

def main():
    print("🚀 Starte BATCH-Sync der Garmin Historie...")
    
    garmin_email = os.environ.get('GARMIN_EMAIL')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')
    
    try:
        garmin = Garmin(garmin_email, garmin_password)
        garmin.login()
        
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        
        existing_data = sheet.get_all_values()
        existing_ids = set([row[0] + row[1] for row in existing_data[1:]]) if len(existing_data) > 1 else set()
        print(f"📊 {len(existing_ids)} vorhandene Einträge überspringe ich.")

        start_index = 0
        batch_size = 40 # Garmin-Batch
        new_entries_count = 0
        all_new_rows = []

        while True:
            print(f"📥 Lade Aktivitäten ab Index {start_index}...")
            activities = garmin.get_activities(start_index, batch_size)
            
            if not activities:
                break 
            
            current_batch_rows = []
            for activity in activities:
                try:
                    start_time = activity.get('startTimeLocal', '')
                    activity_name = activity.get('activityName', 'Aktivität')
                    
                    if start_time + activity_name in existing_ids:
                        continue

                    act_date = start_time[:10]
                    
                    # Gewichtssuche (7-Tage-Fenster)
                    weight = 0
                    try:
                        end_dt = datetime.strptime(act_date, '%Y-%m-%d')
                        start_dt = end_dt - timedelta(days=7)
                        body_data = garmin.get_body_composition(start_dt.isoformat()[:10], act_date)
                        weight_list = body_data.get('dateWeightList', [])
                        if weight_list:
                            weight = round(weight_list[-1].get('weight', 0) / 1000, 2)
                    except: weight = 0

                    # Gesundheit (RHR, Schlaf, HRV)
                    rhr, sleep_hours, hrv = 0, 0, 'N/A'
                    try:
                        stats = garmin.get_stats(act_date)
                        rhr = stats.get('restingHeartRate', 0)
                        
                        sleep_data = garmin.get_sleep_data(act_date)
                        sleep_hours = format_sleep(sleep_data.get('dailySleepDTO', {}).get('sleepTimeSeconds', 0))
                        
                        hrv_data = garmin.get_hrv_data(act_date)
                        hrv = hrv_data.get('hrvSummary', {}).get('lastNightAvg', 'N/A') if hrv_data else 'N/A'
                    except: pass

                    dist_m = activity.get('distance', 0)
                    dur_s = activity.get('duration', 0)
                    dist_km = round(dist_m / 1000, 2)
                    pace, kmh = calculate_speed_and_pace(dist_m, dur_s)
                    
                    row = [
                        start_time, activity_name, 
                        activity.get('activityType', {}).get('typeKey', 'n/a'),
                        dist_km, format_duration(dur_s), pace, kmh,
                        activity.get('averageHR', 0), activity.get('calories', 0),
                        round(activity.get('elevationGain', 0), 0),
                        weight, rhr, hrv, sleep_hours
                    ]
                    
                    current_batch_rows.append(row)
                    print(f"  -> Vorbereitet: {act_date} - {activity_name}")
                    
                except Exception as e:
                    print(f"  ⚠️ Fehler bei {start_time}: {e}")

            # Wenn wir neue Zeilen haben, laden wir sie jetzt für diesen Batch hoch
            if current_batch_rows:
                print(f"⬆️ Lade {len(current_batch_rows)} Zeilen zu Google Sheets hoch...")
                sheet.append_rows(current_batch_rows)
                new_entries_count += len(current_batch_rows)
                print("✅ Batch hochgeladen.")

            start_index += batch_size
            time.sleep(1) # Kleine Pause für Garmin

        print(f"✨ Fertig! Insgesamt {new_entries_count} neue Aktivitäten importiert.")

    except Exception as e:
        print(f"❌ Globaler Fehler: {e}")

if __name__ == "__main__":
    main()
