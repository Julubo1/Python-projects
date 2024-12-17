import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

def url_builder(query, output_file, num_results=5):
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

                    # Check if the link is the specific URL we are interested in
                    if link == "https://bolddata.nl/en/companies/netherlands/oil-companies-netherlands/":
                        # Extract the list of companies from this URL
                        company_list = extract_company_list(link)
                        for company in company_list:
                            company_details = scrape_company_page(company['url'])
                            results.append((company['name'], company['url'], company_details['address'], company_details['phone'], company_details['contact_info']))
                    else:
                        # Scrape the URL to get more details
                        company_details = scrape_company_page(link)
                        results.append((title, link, company_details['address'], company_details['phone'], company_details['contact_info']))
            except Exception as e:
                results.append((title, f"Error: {e}", "No Address Found", "No Phone Found", "No Contact Info Found"))
    except Exception as e:
        print(f"Failed to fetch search results: {e}")

    # Save results to an Excel file with a single worksheet
    if results:
        data = {
            "Company Name": [result[0] for result in results],
            "URL": [result[1] for result in results],
            "Address": [result[2] for result in results],
            "Phone Number": [result[3] for result in results],
            "Contact Info": [result[4] for result in results]
        }
        df = pd.DataFrame(data)
        df.to_excel(output_file, index=False, engine='xlsxwriter')
        print(f"Results saved to {output_file}")
    else:
        print("No results found to save.")

def extract_company_list(url):
    try:
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82',
        }
        content = requests.get(url, headers=headers).text
        soup = BeautifulSoup(content, 'html.parser')

        # Extract the list of companies
        company_list = []
        company_items = soup.find_all('div', class_='company-item')  # Adjust the class name as needed
        for item in company_items:
            name_tag = item.find('h3')
            link_tag = item.find('a', href=True)
            if name_tag and link_tag:
                name = name_tag.text.strip()
                link = link_tag['href']
                company_list.append({'name': name, 'url': link})
        return company_list
    except Exception as e:
        print(f"Failed to extract company list from {url}: {e}")
        return []

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
query = "Hospitals in the Netherlands"

# Use a different filename to test
output_file = f"{query.replace(' ', '_')}.xlsx"
url_builder(query, output_file)