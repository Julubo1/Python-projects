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

    # Fetch available fields for project.project to verify
    fields = models.execute_kw(db, uid, password, 'project.project', 'fields_get', [])

    # Define the fields you need
    required_fields = [
        'id',
        'sequence',
        'name',
        'x_studio_location',
        'x_studio_budget',
        'partner_id',
        'x_studio_many2one_field_h5V6V',
        'date_start',
        'date',
        'user_id',
        'company_id',
        'last_update_status',
        'stage_id',
        'task_count'
    ]

    # Filter out fields that are not available in the project model
    available_fields = [field for field in required_fields if field in fields]

    # Define the context with the desired language
    context = {'lang': 'en_GB'}  # Change 'en_GB' to your desired language code

    # Fetch project.project records with the specified context
    activities = models.execute_kw(db, uid, password, 'project.project', 'search_read', [[]], {
        'fields': available_fields,
        'context': context
    })
    print(f"Fetched {len(activities)} records.")

    # Convert to DataFrame
    df = pd.DataFrame(activities)

    # Remove HTML tags from the 'note' column if it exists
    if 'note' in df.columns:
        df['note'] = df['note'].apply(remove_html_tags)

    # Export to Excel
    df.to_excel('Projects.xlsx', index=False)
    print("Data successfully exported to Projects.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")