import xmlrpc.client
import pandas as pd
import re


# Function to remove HTML tags
def remove_html_tags(text):
    if text is None:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# Connection parameters
url = ""
db = ""
username = ""
password = ""

try:
    # Login
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    # Fetch available fields for helpdesk.ticket to verify
    fields = models.execute_kw(db, uid, password, 'helpdesk.ticket', 'fields_get', [])

    # Define the fields you need
    required_fields = [
        'display_name',
        'team_id',
        'user_id',
        'partner_id',
        'company_id',
        'priority',
        'ticket_type_id',
        'stage_id',
        'create_date',
    ]

    # Filter out fields that are not available in the helpdesk.ticket model
    available_fields = [field for field in required_fields if field in fields]

    # Define the domain to filter out records with "solved" in their stage name
    domain = [
        ['stage_id.name', 'not ilike', '%solved%'],
        ['stage_id.name', 'not ilike', '%cancelled%'],
        ['stage_id.name', 'not ilike', '%Afgewezen%']
    ]

    # Fetch helpdesk.ticket records
    activities = models.execute_kw(db, uid, password, 'helpdesk.ticket', 'search_read', [domain], {
        'fields': available_fields
    })
    print(f"Fetched {len(activities)} records.")

    # Convert to DataFrame
    df = pd.DataFrame(activities)

    # Remove HTML tags from the 'note' column
    if 'note' in df.columns:
        df['note'] = df['note'].apply(remove_html_tags)

    # Export to Excel
    df.to_excel('Helpdesk.xlsx', index=False)
    print("Data successfully exported to Helpdesk.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")