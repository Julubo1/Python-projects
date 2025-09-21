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

# Login
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Fetch available fields for repair to verify
fields = models.execute_kw(db, uid, password, 'repair.order', 'fields_get', [])
print("Available fields in repair.order:", fields.keys())

# Set the language context
context = {'lang': 'en_GB'}  # Change 'en_GB' to your desired language code

# Define the fields you need
required_fields = [
    'id',
    'name',
    'schedule_date',
    'product_id',
    'x_studio_serial_number',
    'subcontract_product_partner',
    'partner_id',
    'address_id',
    'sale_order_id',
    'company_id',
    'state',
    'untaxed_amount',
    'currency_id',
    'activity_ids'
]

# Filter out fields that are not available in the repair.order model
available_fields = [field for field in required_fields if field in fields]
print("Available required fields:", available_fields)

# Fetch repair.order records
try:
    repairs = models.execute_kw(db, uid, password, 'repair.order', 'search_read', [[]], {
        'fields': available_fields, 'context' : context
    })
    print(f"Fetched {len(repairs)} repair records.")
    print("Sample repair record:", repairs[0])  # Print a sample record for debugging

    # Fetch activity_ids separately
    activity_ids = [activity_id for repair in repairs for activity_id in repair.get('activity_ids', [])]
    if activity_ids:
        activity_fields = ['id', 'create_uid', 'summary', 'note']
        activities = models.execute_kw(db, uid, password, 'mail.activity', 'search_read', [[('id', 'in', activity_ids)]], {
            'fields': activity_fields
        })
        activity_dict = {activity['id']: activity for activity in activities}
    else:
        activity_dict = {}

    # Prepare data for export
    data = []
    for repair in repairs:
        repair_data = {
            'Repair Order ID': repair.get('id'),
            'Name': repair.get('name', ''),
            'Schedule Date': repair.get('schedule_date', ''),
            'Product ID': repair.get('product_id', [None, ''])[0] if isinstance(repair.get('product_id'), list) else None,
            'Product Name': repair.get('product_id', [None, ''])[1] if isinstance(repair.get('product_id'), list) else '',
            'Serial Number': repair.get('x_studio_serial_number', ''),
            'Subcontract Product Partner': repair.get('subcontract_product_partner', ''),
            'Partner ID': repair.get('partner_id', [None, ''])[0] if isinstance(repair.get('partner_id'), list) else None,
            'Partner Name': repair.get('partner_id', [None, ''])[1] if isinstance(repair.get('partner_id'), list) else '',
            'Address ID': repair.get('address_id', [None, ''])[0] if isinstance(repair.get('address_id'), list) else None,
            'Address Name': repair.get('address_id', [None, ''])[1] if isinstance(repair.get('address_id'), list) else '',
            'Sales Order ID': repair.get('sale_order_id', [None, ''])[0] if isinstance(repair.get('sale_order_id'), list) else None,
            'Sales Order Name': repair.get('sale_order_id', [None, ''])[1] if isinstance(repair.get('sale_order_id'), list) else '',
            'Company ID': repair.get('company_id', [None, ''])[0] if isinstance(repair.get('company_id'), list) else None,
            'Company Name': repair.get('company_id', [None, ''])[1] if isinstance(repair.get('company_id'), list) else '',
            'State': repair.get('state', ''),
            'Untaxed Amount': repair.get('untaxed_amount', 0.0),
            'Currency ID': repair.get('currency_id', [None, ''])[0] if isinstance(repair.get('currency_id'), list) else None,
            'Currency Name': repair.get('currency_id', [None, ''])[1] if isinstance(repair.get('currency_id'), list) else '',
            'Activity Create UID': [],
            'Activity Summary': [],
            'Activity Note': []
        }

        # Populate activity details
        for activity_id in repair.get('activity_ids', []):
            activity = activity_dict.get(activity_id, {})
            repair_data['Activity Create UID'].append(activity.get('create_uid', [None, ''])[1] if activity.get('create_uid') else '')
            repair_data['Activity Summary'].append(activity.get('summary', ''))
            repair_data['Activity Note'].append(remove_html_tags(activity.get('note', '')))

        data.append(repair_data)

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Export to Excel
    df.to_excel('RepairModule.xlsx', index=False)
    print("Data successfully exported to RepairModule.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")