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

# Function to gather activity details
def gather_activity_details(activities, activity_dict):
    activity_users = []
    activity_notes = []
    activity_create_dates = []
    activity_summaries = []
    for activity_id in activities:
        activity_details = activity_dict.get(activity_id, {})
        user_id = str(activity_details.get('user_id', [0, ''])[1])  # Convert to string
        activity_users.append(user_id)
        note = activity_details.get('note', '')
        clean_note = remove_html_tags(note)  # Remove HTML tags
        activity_notes.append(clean_note)
        create_date = str(activity_details.get('create_date', ''))  # Convert to string
        activity_create_dates.append(create_date)
        summary = str(activity_details.get('summary', ''))  # Convert to string
        activity_summaries.append(summary)
    return activity_users, activity_notes, activity_create_dates, activity_summaries


# Login
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Set the language context
context = {'lang': 'en_GB'}  # Change 'en_GB' to your desired language code

# Fetch purchase order records
try:
    purchase_orders = models.execute_kw(db, uid, password, 'purchase.order', 'search_read', [[]], {
        'fields': [
            'id',
            'name',
            'state',
            'partner_id',
            'company_id',
            'product_id',
            'user_id',
            'date_order',
            'x_studio_business_line',
            'origin',
            'amount_total',
            'picking_status',
            'payment_term_id',
            'currency_id',
            'currency_rate',
            'amount_untaxed',
            'po_sent_date',
            'date_approve',
            'date_planned'
        ],
        'context': context
    })
    print(f"Fetched {len(purchase_orders)} purchase orders.")
except Exception as e:
    print(f"An error occurred while fetching purchase orders: {e}")
    exit(1)

# Regular expression to extract document numbers from the origin field
doc_number_pattern = re.compile(r'(SO[1-9]-\d{7}|Q[1-9]-\d{7})')

# Prepare data for export
data = []
for po in purchase_orders:
    origin = str(po.get('origin', ''))  # Convert origin to string
    related_doc_number = None

    # Extract document numbers from the origin field
    matches = doc_number_pattern.findall(origin)
    if matches:
        # Assuming the first match is the correct document number
        related_doc_number = matches[0]
    else:
        # Use the original origin value if no match is found
        related_doc_number = po.get('origin', '')

    po_data = {
        'Purchase Order ID': po['id'],
        'Purchase Order Name': po['name'],
        'State': po['state'],
        'Partner ID': po['partner_id'][0] if po['partner_id'] else None,
        'Partner Name': po['partner_id'][1] if po['partner_id'] else None,
        'Company ID': po['company_id'][0] if po['company_id'] else None,
        'Company Name': po['company_id'][1] if po['company_id'] else None,
        'Product ID': po['product_id'][0] if po['product_id'] else None,
        'Product Name': po['product_id'][1] if po['product_id'] else None,
        'User ID': po['user_id'][0] if po['user_id'] else None,
        'User Name': po['user_id'][1] if po['user_id'] else None,
        'Date Order': po['date_order'],
        'Business Line': po['x_studio_business_line'],
        'Origin': po['origin'],
        'Amount Total': po['amount_total'],
        'Picking Status': po['picking_status'],
        'Payment Term ID': po['payment_term_id'][0] if po['payment_term_id'] else None,
        'Payment Term Name': po['payment_term_id'][1] if po['payment_term_id'] else None,
        'Currency ID': po['currency_id'][0] if po['currency_id'] else None,
        'Currency Name': po['currency_id'][1] if po['currency_id'] else None,
        'Currency Rate': po['currency_rate'],
        'Amount Untaxed': po['amount_untaxed'],
        'PO Sent Date': po['po_sent_date'],
        'Date Approve': po['date_approve'],
        'Date Planned': po['date_planned'],
        'Related Document Number': related_doc_number
    }

    if related_doc_number == po.get('origin', ''):
        # Debugging: Print no related document number found
        print(f"Purchase Order {po['name']} has no related document number in origin, using original value: {related_doc_number}")
    else:
        # Debugging: Print the related document number
        print(f"  - Found related document number: {related_doc_number}")

    data.append(po_data)

# Convert to DataFrame
df = pd.DataFrame(data)

# Export to Excel
try:
    df.to_excel('PurchaseModule.xlsx', index=False)
    print("Data successfully exported to PurchaseModule.xlsx.")
except Exception as e:
    print(f"An error occurred while exporting to Excel: {e}")