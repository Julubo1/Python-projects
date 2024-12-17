import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

def url_builder(query, output_file, num_results=10):
    print("Scanning...")

    url = 'https://www.google.com/search'  # Search Engine Used
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82',
    }

    results = []  # Storage for created list. This gets converted into a CSV

    parameters = {'q': query}
    try:
        content = requests.get(url, headers=headers, params=parameters).text
        soup = BeautifulSoup(content, 'html.parser')
        search_results = soup.find_all('div', class_='tF2Cxc')  # Google search result container

        for result_div in search_results[:num_results]:  # Limit to top N results
            try:
                link_tag = result_div.find('a')
                if link_tag and 'href' in link_tag.attrs:
                    link = link_tag['href']
                    # Extract the actual URL from the Google link
                    if link.startswith('/url?q='):
                        link = link[7:].split('&')[0]
                    title_tag = result_div.find('h3')
                    title = title_tag.text if title_tag else "No Title Found"

                    # Scrape the URL to get more details
                    company_details = scrape_company_page(link)
                    results.append((title, link, company_details['address'], company_details['phone'], company_details['contact_info']))
            except Exception as e:
                results.append((title, f"Error: {e}", "No Address Found", "No Phone Found", "No Contact Info Found"))
    except Exception as e:
        print(f"Failed to fetch search results: {e}")

    # Save results to an Excel file with each result in a separate worksheet
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        for i, result in enumerate(results):
            title, link, address, phone, contact_info = result
            data = {
                "Company Name": [title],
                "URL": [link],
                "Address": [address],
                "Phone Number": [phone],
                "Contact Info": [contact_info]
            }
            df = pd.DataFrame(data)
            sheet_name = f"Result_{i+1}"
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Results saved to {output_file}")


def scrape_company_page(url):
    try:
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82',
        }
        content = requests.get(url, headers=headers).text
        soup = BeautifulSoup(content, 'html.parser')

        # Extract address
        address = "No Address Found"
        address_tag = soup.find('address')
        if address_tag:
            address = address_tag.get_text(separator=' ', strip=True)
        else:
            # Fallback to searching for a div with class 'address'
            address_div = soup.find('div', class_=re.compile(r'address', re.IGNORECASE))
            if address_div:
                address = address_div.get_text(separator=' ', strip=True)

        # Extract phone number
        phone = "No Phone Found"
        phone_tag = soup.find('a', href=re.compile(r'tel:', re.IGNORECASE))
        if phone_tag:
            phone = phone_tag.get_text(strip=True)
        else:
            # Fallback to searching for a span with class 'phone'
            phone_span = soup.find('span', class_=re.compile(r'phone', re.IGNORECASE))
            if phone_span:
                phone = phone_span.get_text(strip=True)

        # Extract contact information
        contact_info = "No Contact Info Found"
        contact_info_tag = soup.find('a', href=re.compile(r'mailto:', re.IGNORECASE))
        if contact_info_tag:
            contact_info = contact_info_tag.get_text(strip=True)
        else:
            # Fallback to searching for a div with class 'contact'
            contact_info_div = soup.find('div', class_=re.compile(r'contact', re.IGNORECASE))
            if contact_info_div:
                contact_info = contact_info_div.get_text(separator=' ', strip=True)

        return {'address': address, 'phone': phone, 'contact_info': contact_info}
    except Exception as e:
        return {'address': f"Error scraping {url}: {e}", 'phone': f"Error scraping {url}: {e}", 'contact_info': f"Error scraping {url}: {e}"}

# Example query
query = "RT Centers in the Netherlands"

# Use a different filename to test
output_file = f"{query.replace(' ', '_')}.xlsx"
url_builder(query, output_file)