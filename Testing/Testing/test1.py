import requests
from bs4 import BeautifulSoup
import csv
import os
import re

def url_builder(example, output_file): # Builds URLs for the given search terms and saves the results to a CSV file.
    print("Scanning...")

    url = 'https://www.google.com/search' # Search Engine Used
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82',
    }

    result = [] # Storage for created list. This gets converted into a CSV

    # 
    for org_name in example:
        parameters = {'q': org_name}
        try:
            content = requests.get(url, headers=headers, params=parameters).text
            soup = BeautifulSoup(content, 'html.parser')
            search_result = soup.find(id='search')
            first_link = search_result.find('a') if search_result else None
            link = first_link['href'] if first_link and 'href' in first_link.attrs else "No Link Found"
            result.append(link)
        except Exception as e:
            result.append(f"Error: {e}")

    # Save results as .csv in the current working directory
    output_path = os.path.join(os.getcwd(), output_file)
    with open(output_path, "w", newline="", encoding="utf-8") as csv_converter:
        writer = csv.writer(csv_converter)
        writer.writerow(["Search Term", "URL", "Emails", "Phones"])
        for org_name, link in zip(example, result):
            if not link.startswith("http"):
                writer.writerow([org_name, link, "Couldn't access site", "Couldn't access site"])
            else:
                emails, phones = scrape_contact_info(link)
                writer.writerow([org_name, link, emails, phones])

    print(f"Results saved to {output_path}")

def scrape_contact_info(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract email addresses
            emails = set(re.findall(r'[\w\.-]+@[\w\.-]+', soup.text))
            
            # Extract phone numbers (simple regex for illustration)
            phones = set(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', soup.text))
            
            emails_str = ", ".join(emails) if emails else "No Emails Found"
            phones_str = ", ".join(phones) if phones else "No Phones Found"
            
            return emails_str, phones_str
        else:
            return "Couldn't access site", "Couldn't access site"
    except Exception as e:
        return "Couldn't access site", "Couldn't access site"

# Example list. Simplify adding/removing entries
example = [
    "NRG Nuclear",
    "Ommelander Ziekenhuisgroep Delfzicht Ziekenhuis",
    "Ommelander Ziekenhuisgroep Lucas Ziekenhuis",
    "Martini Ziekenhuis van Swieten",
    "Refaja Ziekenhuis Stadskanaa",
    "Flevoziekenhuis",
    "IJsselmeer Ziekenhuizen Zuiderzeeziekenhuis",
    "IJsselmeer Ziekenhuizen Dokter J.H. Jansenziekenhuis",
    "Diakonessenhuis Utrecht",
    "Diakonessenhuis Zeist",
    "Meander Medisch Centrum Amersfoort Lichtenberg",
    "Meander Medisch Centrum Amersfoort Elisabeth",
    "St. Antonius Ziekenhuis Oudenrijn",
    "St. Antonius Ziekenhuis Nieuwegein",
    "St. Antonius Ziekenhuis Overvecht",
    "Zuwe Zuwe Hofpoort Ziekenhuis",
    "BovenIJ Ziekenhuis",
    "SUN Nuclear"
]

url_builder(example, "pleasework_test.csv") # url_builder(list, filename)
