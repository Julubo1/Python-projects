import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import json 

# --- FUNCTIE OM DETAILS VAN EEN INDIVIDUELE PRAKTIJKPAGINA TE HALEN ---
def get_details(practice_url, headers):
    details = {
        'Adres': 'N/A',
        'Postcode': 'N/A',
        'Stad': 'N/A',
        'Telefoonnummer': 'N/A'
    }
    try:
        response = requests.get(practice_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- NIEUWE, BETROUWBARE METHODE: JSON-LD SCRIPT VINDEN ---
        json_script = soup.find('script', type='application/ld+json')
        
        if json_script:
            data = json.loads(json_script.string) # Converteer de tekst naar een Python dictionary
            
            # Haal de data uit het JSON-object
            details['Telefoonnummer'] = data.get('telephone', 'N/A')
            
            if 'address' in data and isinstance(data['address'], dict):
                address_data = data['address']
                details['Adres'] = address_data.get('streetAddress', 'N/A')
                details['Postcode'] = address_data.get('postalCode', 'N/A')
                details['Stad'] = address_data.get('addressLocality', 'N/A')
                
    except requests.exceptions.RequestException as e:
        print(f"  -> Fout bij ophalen details van {practice_url}: {e}")
    except json.JSONDecodeError:
        print(f"  -> Kon JSON niet verwerken op pagina: {practice_url}")
    
    # Een kleine pauze om de server niet te overbelasten
    time.sleep(0.2)
    return details

# --- HOOFDSCRIPT (grotendeels ongewijzigd) ---
BASE_URL = "https://www.zorgkaartnederland.nl/huisartsenpraktijk"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

alle_praktijken = []
TOTAAL_PAGINAS = 243 

for pagina_nummer in range(1, TOTAAL_PAGINAS + 1):
    if pagina_nummer == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}/pagina{pagina_nummer}"
    
    print(f"Scrapen van overzichtspagina {pagina_nummer}/{TOTAAL_PAGINAS}...")

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        praktijk_cards = soup.find_all('div', class_='filter-result')
        if not praktijk_cards:
            print(f"  -> Geen praktijken gevonden op pagina {pagina_nummer}.")
            continue

        for card in praktijk_cards:
            naam_element = card.find('a', class_='filter-result__name')
            if not naam_element:
                continue
                
            naam = naam_element.get_text(strip=True)
            practice_relative_link = naam_element['href']
            practice_full_link = urljoin(BASE_URL, practice_relative_link)

            print(f"  -> Ophalen details voor: {naam}")
            details = get_details(practice_full_link, HEADERS)
            
            alle_praktijken.append({
                'Naam': naam,
                'Adres': details['Adres'],
                'Postcode': details['Postcode'],
                'Stad': details['Stad'],
                'Telefoonnummer': details['Telefoonnummer']
            })
            
    except requests.exceptions.RequestException as e:
        print(f"Fout bij het ophalen van overzichtspagina {pagina_nummer}: {e}")
    
    time.sleep(1)

# --- DataFrame opslaan ---
df = pd.DataFrame(alle_praktijken)
if not df.empty:
    try:
        df.to_csv('huisartsenpraktijken_details.csv', index=False, encoding='utf-8-sig')
        print("\nScraping voltooid!")
        print(f"Er zijn {len(df)} praktijken opgeslagen in 'huisartsenpraktijken_details.csv'.")
    except Exception as e:
        print(f"Fout bij het opslaan naar CSV: {e}")
else:
    print("\nScraping voltooid, maar er zijn geen gegevens gevonden.")
