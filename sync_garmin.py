import os
from garminconnect import Garmin
from datetime import datetime

def main():
    print("🔍 STARTE GARMIN DEBUG-MODUS...")
    
    garmin_email = os.environ.get('GARMIN_EMAIL')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    
    if not all([garmin_email, garmin_password]):
        print("❌ Fehler: GARMIN_EMAIL oder GARMIN_PASSWORD nicht gesetzt.")
        return
    
    try:
        garmin = Garmin(garmin_email, garmin_password)
        garmin.login()
        print("✅ Login erfolgreich.\n")
        
        # 1. USER PROFIL CHECK
        print("--- [1] USER PROFIL ROHDATEN ---")
        profile = garmin.get_user_profile()
        # Wir geben nur die interessanten Keys aus, um dich nicht mit Daten zu überfluten
        for key in ['weight', 'weightInGrams', 'defaultUnitSystem', 'height']:
            print(f"Feld '{key}': {profile.get(key)}")
        
        if 'userProfile' in profile:
            print(f"Feld 'userProfile -> weight': {profile['userProfile'].get('weight')}")
        print("-" * 30 + "\n")

        # 2. BODY COMPOSITION CHECK (Heute)
        today = datetime.now().date().isoformat()
        print(f"--- [2] BODY COMPOSITION FÜR HEUTE ({today}) ---")
        try:
            body_data = garmin.get_body_composition(today)
            print(f"Rohdaten: {body_data}")
        except Exception as e:
            print(f"Fehler bei Body Composition: {e}")
        print("-" * 30 + "\n")

        # 3. AKTIVITÄTS-CHECK (Letzte Aktivität)
        print("--- [3] LETZTE AKTIVITÄT ROHDATEN ---")
        activities = garmin.get_activities(0, 1)
        if activities:
            act = activities[0]
            print(f"Name: {act.get('activityName')}")
            print(f"Verfügbare Felder in der Aktivität: {list(act.keys())[:15]}...") # Nur die ersten 15 Keys
        else:
            print("Keine Aktivitäten gefunden.")
        print("-" * 30 + "\n")

    except Exception as e:
        print(f"❌ Allgemeiner Fehler: {e}")

if __name__ == "__main__":
    main()
