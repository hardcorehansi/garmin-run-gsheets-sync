import os
import json
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

def create_dashboard():
    print("📊 Erstelle kompaktes Jahres-Dashboard (Hauptkategorien)...")
    
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')
    
    if not all([google_creds_json, sheet_id]):
        print("❌ Fehler: Google Credentials oder Sheet ID fehlen!")
        return

    creds_dict = json.loads(google_creds_json)
    creds = Credentials.from_service_account_info(
        creds_dict, 
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    client = gspread.authorize(creds)
    
    # Mapping-Logik für Hauptkategorien
    CATEGORY_MAP = {
        # Cycling
        'cycling': 'Cycling', 'road_biking': 'Cycling', 'gravel_cycling': 'Cycling', 
        'virtual_ride': 'Cycling', 'mountain_biking': 'Cycling',
        # Running
        'running': 'Running', 'street_running': 'Running', 'trail_running': 'Running', 
        'track_running': 'Running',
        # Swimming
        'lap_swimming': 'Swimming', 'open_water_swimming': 'Swimming', 'swimming': 'Swimming',
        # Hiking & Walking
        'hiking': 'Hiking/Walking', 'walking': 'Hiking/Walking',
        # Fitness & Indoor
        'strength_training': 'Fitness/Indoor', 'indoor_cardio': 'Fitness/Indoor', 
        'pilates': 'Fitness/Indoor', 'mobility': 'Fitness/Indoor', 'yoga': 'Fitness/Indoor',
        # Wintersport
        'backcountry_skiing': 'Skiing', 'resort_skiing': 'Skiing', 'nordic_skiing': 'Skiing'
    }

    try:
        main_sheet = client.open_by_key(sheet_id).sheet1
        records = main_sheet.get_all_records()
        
        if not records:
            print("⚠️ Keine Daten gefunden.")
            return
            
        df = pd.DataFrame(records)
        
        # 1. Daten-Vorbereitung
        df['Datum'] = pd.to_datetime(df['Datum'], errors='coerce')
        df = df.dropna(subset=['Datum'])
        df['Jahr'] = df['Datum'].dt.year
        
        # 2. Einheiten korrigieren & sicherstellen (KM und HM)
        df['km'] = pd.to_numeric(df['km'], errors='coerce').fillna(0)
        df['HM'] = pd.to_numeric(df['HM'], errors='coerce').fillna(0)

        # 3. Hauptkategorie zuweisen
        df['Kategorie'] = df['Typ'].apply(lambda x: CATEGORY_MAP.get(str(x).lower(), 'Other'))

        # 4. Aggregation nach Jahr und Hauptkategorie
        summary = df.groupby(['Jahr', 'Kategorie']).agg({
            'km': 'sum',
            'HM': 'sum'
        }).reset_index()

        # 5. Runden für saubere Darstellung
        summary['km'] = summary['km'].apply(lambda x: round(float(x), 2))
        summary['HM'] = summary['HM'].apply(lambda x: int(float(x)))

        # Sortierung: Neuestes Jahr zuerst, dann nach KM-Leistung
        summary = summary.sort_values(by=['Jahr', 'km'], ascending=[False, False])

        # Dashboard-Blatt ansteuern
        try:
            dashboard_sheet = client.open_by_key(sheet_id).worksheet("Dashboard")
        except gspread.exceptions.WorksheetNotFound:
            dashboard_sheet = client.open_by_key(sheet_id).add_worksheet(title="Dashboard", rows="100", cols="5")

        dashboard_sheet.clear()
        
        # Header schreiben
        header = [
            ["SPORT-DASHBOARD: JAHRESÜBERSICHT"],
            ["Einheit: Kilometer (km) / Höhenmeter (m)"],
            ["Stand:", pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')],
            []
        ]
        
        table_header = [["Jahr", "Kategorie", "Gesamt KM", "Gesamt HM"]]
        table_data = summary.values.tolist()
        
        # Alles ins Sheet schreiben
        dashboard_sheet.update("A1", header + table_header + table_data)
        
        print(f"✅ Dashboard erfolgreich aktualisiert. Alles auf KM und HM bereinigt.")

    except Exception as e:
        print(f"❌ Fehler im Dashboard-Skript: {e}")

if __name__ == "__main__":
    create_dashboard()
