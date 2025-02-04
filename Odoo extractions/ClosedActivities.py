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

    # Fetch available fields for mail.activity to verify
    fields = models.execute_kw(db, uid, password, 'mail.message', 'fields_get', [])

    # Define the fields you need
    required_fields = [
        'date',
        'subject',
        'author_id',
        'model',
        'res_id',
        'message_type',
        'subtype_id',
        'body',

    ]

    # Filter out fields that are not available in the mail.activity model
    available_fields = [field for field in required_fields if field in fields]

    # Fetch mail.activity records with a domain filter for system notifications
    domain = [
        ('message_type', '=', 'notification'),
        ('date', '>=', '2025-01-01'),
        ('date', '<', '2026-01-01')
    ]
    activities = models.execute_kw(db, uid, password, 'mail.message', 'search_read', [domain], {
        'fields': available_fields
    })
    print(f"Fetched {len(activities)} System Notification records.")

    # Convert to DataFrame
    df = pd.DataFrame(activities)

    # Remove HTML tags from the 'note' column
    if 'body' in df.columns:
        df['body'] = df['body'].apply(remove_html_tags)

    # Export to Excel
    df.to_excel('ClosedActivities.xlsx', index=False)
    print("Data successfully exported to ClosedActivities.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")