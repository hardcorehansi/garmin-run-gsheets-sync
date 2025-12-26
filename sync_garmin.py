import os
import json
from garminconnect import Garmin
from datetime import datetime, timedelta

def main():
    print("🔬 START DEEP-DIVE TEST (Gewicht & Schlaf-Pfad)...")
    
    garmin_email = os.environ.get('GARMIN_EMAIL')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    
    try:
        garmin = Garmin(garmin_email, garmin_password)
        garmin.login()
        print("✅ Login erfolgreich.\n")
        
        # TEST 1: User Settings (Das 'userData' Versteck)
        print("--- [TEST 1] USER SETTINGS ---")
        try:
            settings = garmin.get_user_settings()
            user_data = settings.get('userData', {})
            print(f"Gewicht in userData: {user_data.get('weight')}")
            print(f"Größe in userData: {user_data.get('height')}")
        except Exception as e:
            print(f"Fehler in Test 1: {e}")
        print("-" * 30 + "\n")

        # TEST 2: Body Composition (7-Tage Rückblick)
        # Wenn heute nichts drin steht, schauen wir eine Woche zurück
        print("--- [TEST 2] BODY COMPOSITION (7 TAGE) ---")
        try:
            today = datetime.now().date()
            seven_days_ago = (today - timedelta(days=7)).isoformat()
            body_data = garmin.get_body_composition(seven_days_ago, today.isoformat())
            
            # Wir prüfen die Liste der Einträge
            weight_list = body_data.get('dateWeightList', [])
            print(f"Anzahl Einträge letzte 7 Tage: {len(weight_list)}")
            if weight_list:
                print(f"Letzter Gewichtswert in Liste: {weight_list[-1].get('weight')}")
        except Exception as e:
            print(f"Fehler in Test 2: {e}")
        print("-" * 30 + "\n")

        # TEST 3: Schlaf-Detailstruktur
        print("--- [TEST 3] SCHLAF-STRUKTUR ---")
        try:
            today_str = datetime.now().date().isoformat()
            sleep = garmin.get_sleep_data(today_str)
            # Wir schauen, wo genau die Sekunden stecken
            dto = sleep.get('dailySleepDTO', {})
            print(f"Schlaf-Sekunden (dailySleepDTO): {dto.get('sleepTimeSeconds')}")
            print(f"Schlaf-Sekunden (nachrangig): {sleep.get('sleepSearchTimeSec')}")
        except Exception as e:
            print(f"Fehler in Test 3: {e}")
        print("-" * 30 + "\n")

    except Exception as e:
        print(f"❌ Kritischer Fehler: {e}")

if __name__ == "__main__":
    main()
