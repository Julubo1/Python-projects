import xmlrpc.client
import pandas as pd
import re
import logging


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

    # Fetch available fields for mail.activity
    activity_fields_info = models.execute_kw(db, uid, password, 'mail.activity', 'fields_get', [])
    available_activity_fields = list(activity_fields_info.keys())

    # Print available fields for mail.activity
    logging.info(f"Available fields in mail.activity: {available_activity_fields}")

    # Define the fields you need from res.partner
    partner_fields = [
        'display_name',
        'name',
        'lastname',
        'firstname',
        'phone',
        'email',
        'industry_id',
        'write_date',
        'write_uid',
        'comment',
        'activity_date_deadline',
        'activity_summary',  # This field might not exist
        'category_id',
        'is_company',
        'activity_type_id',
        'country_id',
        'x_oem_vendor_ids',
        'x_studio_oem',
        'x_studio_oem_1',
        'x_studio_oem_2',
        'id',
        'x_studio_2way_communication_established',
        'activity_ids',
    ]

    # Fetch res.partner records
    partners = models.execute_kw(db, uid, password, 'res.partner', 'search_read', [[]], {
        'fields': partner_fields
    })
    logging.info(f"Fetched {len(partners)} Partner records.")

    # Define the fields you need from mail.activity
    # Ensure these fields exist in the mail.activity model
    activity_fields = [
        'date_deadline',
        'note',
        'user_id',
        'create_date',
        'create_uid',
        'summary',  # Use 'summary' if it exists in the mail.activity model
    ]

    # Prepare a list to store the combined data
    combined_data = []

    # Define batch size
    batch_size = 100

    # Process partners in batches
    for i in range(0, len(partners), batch_size):
        batch_partners = partners[i:i + batch_size]
        logging.info(f"Processing batch {i // batch_size + 1} of {len(partners) // batch_size + 1}")

        for partner in batch_partners:
            # Fetch related mail.activity records
            activity_ids = partner.get('activity_ids', [])
            if activity_ids:
                activities = models.execute_kw(db, uid, password, 'mail.activity', 'search_read', [[['id', 'in', activity_ids]]], {
                    'fields': activity_fields
                })

                # Combine the partner data with each activity data
                for activity in activities:
                    combined_record = partner.copy()
                    combined_record.update({
                        'activity_ids/date_deadline': activity.get('date_deadline'),
                        'activity_ids/note': activity.get('note'),
                        'activity_ids/user_id': activity.get('user_id', [False, ''])[1],  # Get the display name of the user
                        'activity_ids/create_date': activity.get('create_date'),
                        'activity_ids/create_uid': activity.get('create_uid', [False, ''])[1],  # Get the display name of the user
                        'activity_ids/summary': activity.get('summary'),  # Use 'summary' if it exists
                    })
                    combined_data.append(combined_record)
            else:
                # If no activities, add the partner record without activity details
                combined_record = partner.copy()
                combined_record.update({
                    'activity_ids/date_deadline': None,
                    'activity_ids/note': None,
                    'activity_ids/user_id': None,
                    'activity_ids/create_date': None,
                    'activity_ids/create_uid': None,
                    'activity_ids/summary': None,  # Use 'summary' if it exists
                })
                combined_data.append(combined_record)

    # Convert to DataFrame
    df = pd.DataFrame(combined_data)

    # Remove HTML tags from the 'activity_ids/note' column
    if 'activity_ids/note' in df.columns:
        df['activity_ids/note'] = df['activity_ids/note'].apply(remove_html_tags)

    # Export to Excel
    df.to_excel('Contacts.xlsx', index=False)
    logging.info("Data successfully exported to Contacts.xlsx.")

except Exception as e:
    logging.error(f"An error occurred: {e}")