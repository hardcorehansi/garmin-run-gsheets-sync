import os
import json
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

def create_dashboard():
    print("📊 Analysiere Daten für das Jahres-Dashboard...")
    
    # Umgebungsvariablen laden
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')
    
    if not all([google_creds_json, sheet_id]):
        print("❌ Fehlende Google Credentials oder Sheet ID!")
        return

    # Google Sheets Verbindung
    creds_dict = json.loads(google_creds_json)
    creds = Credentials.from_service_account_info(
        creds_dict, 
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    client = gspread.authorize(creds)
    
    try:
        # Haupt-Datenblatt öffnen (Tabellenblatt1)
        main_sheet = client.open_by_key(sheet_id).sheet1
        records = main_sheet.get_all_records()
        
        if not records:
            print("⚠️ Keine Daten im Hauptblatt gefunden.")
            return
            
        df = pd.DataFrame(records)
        
        # 1. Datenbereinigung
        # Datum in echtes Datum umwandeln
        df['Datum'] = pd.to_datetime(df['Datum'], errors='coerce')
        df = df.dropna(subset=['Datum']) # Zeilen ohne Datum entfernen
        df['Jahr'] = df['Datum'].dt.year
        
        # Numerische Spalten sicherstellen
        for col in ['km', 'kcal', 'Gewicht', 'HM']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 2. Aggregation: Statistiken pro Jahr und Sportart
        summary = df.groupby(['Jahr', 'Typ']).agg({
            'km': 'sum',
            'kcal': 'sum',
            'HM': 'sum',
            'Gewicht': lambda x: round(x[x > 0].mean(), 2) if any(x > 0) else 0
        }).reset_index()

        # Sortierung: Neuestes Jahr zuerst
        summary = summary.sort_values(by=['Jahr'], ascending=False)

        # 3. Dashboard-Blatt aktualisieren
        try:
            # Prüfen ob Blatt existiert, sonst erstellen
            dashboard_sheet = client.open_by_key(sheet_id).worksheet("Dashboard")
        except gspread.exceptions.WorksheetNotFound:
            dashboard_sheet = client.open_by_key(sheet_id).add_worksheet(title="Dashboard", rows="100", cols="10")

        dashboard_sheet.clear()
        
        # Header und Daten vorbereiten
        header = [["GARMIN JAHRES-DASHBOARD (Automatisch aktualisiert)"], 
                  ["Stand:", pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')], 
                  []]
        
        # Spaltennamen für die Tabelle
        table_header = [["Jahr", "Sportart", "Gesamt KM", "Gesamt Kcal", "Höhenmeter", "Ø Gewicht"]]
        
        # Daten in Liste umwandeln
        table_data = summary.values.tolist()
        
        # Alles ins Sheet schreiben
        dashboard_sheet.update("A1", header + table_header + table_data)
        
        print(f"✅ Dashboard erfolgreich aktualisiert! ({len(table_data)} Einträge)")

    except Exception as e:
        print(f"❌ Fehler beim Erstellen des Dashboards: {e}")

if __name__ == "__main__":
    create_dashboard()
