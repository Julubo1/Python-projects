import requests
from bs4 import BeautifulSoup
import csv

def url_builder(example, output_file):
    """
    Builds URLs for the given search terms and saves the results to a CSV file.

    Args:
        example (list): A list of search terms.
        output_file (str): The path to the output CSV file.
    """
    url = 'https://www.google.com/search'
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82',
    }

    result = []

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

    # Save results to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as csv_converter:
        writer = csv.writer(csv_converter)
        writer.writerow(["Search Term", "URL"])
        writer.writerows(zip(example, result))

    print(f"Results saved to {output_file}")

# Example usage:
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
    "BovenIJ Ziekenhuis"
]

url_builder(example, "pleasework.csv")
