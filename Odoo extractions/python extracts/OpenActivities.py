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
    fields = models.execute_kw(db, uid, password, 'mail.activity', 'fields_get', [])

    # Define the fields you need
    required_fields = [
        'res_model_id',
        'res_name',
        'related_model_instance',
        'create_date',
        'create_uid',
        'summary',
        'note',
        'date_deadline',
        'team_user_id',
        'state',
        'team_id',
        'res_model',
        'res_id',
    ]

    # Filter out fields that are not available in the mail.activity model
    available_fields = [field for field in required_fields if field in fields]

    # Fetch mail.activity records
    activities = models.execute_kw(db, uid, password, 'mail.activity', 'search_read', [[]], {
        'fields': available_fields
    })
    print(f"Fetched {len(activities)} Open Activity records.")

    # Convert to DataFrame
    df = pd.DataFrame(activities)

    # Remove HTML tags from the 'note' column
    if 'note' in df.columns:
        df['note'] = df['note'].apply(remove_html_tags)

    # Export to Excel
    df.to_excel('OpenActivities.xlsx', index=False)
    print("Data successfully exported to OpenActivities.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")