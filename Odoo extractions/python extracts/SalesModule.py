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

try:
    # Login
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    # Set the language context
    context = {'lang': 'en_GB'}  # Change 'en_GB' to your desired language code

    # Fetch sale order records
    orders = models.execute_kw(db, uid, password, 'sale.order', 'search_read', [[]], {
        'fields': [
            'id',
            'name',
            'validity_date',
            'x_studio_verwachte_orderdatum',
            'partner_id',
            'activity_ids',
            'activity_date_deadline',
            'team_id',
            'user_id',
            'company_id',
            'x_studio_slagingskans_1',
            'x_studio_related_field_E2wwo',
            'amount_total',
            'state',
            'opportunity_id',
            'commitment_date',
            'amount_untaxed',
            'currency_id',
            'currency_rate',
            'x_studio_forecast',
            'payment_term_id',
            'invoice_status',
            'partner_shipping_id',
            'date_order',
            'x_studio_rd_poc',
            'client_order_ref',
        ],
        'context': context
    })

    # Extract opportunity_ids, partner_ids, and activity_ids
    opportunity_ids = [order['opportunity_id'][0] for order in orders if order['opportunity_id']]
    partner_ids = [order['partner_id'][0] for order in orders if order['partner_id']]
    activity_ids = [activity_id for order in orders for activity_id in order['activity_ids']]

    # Fetch additional fields from crm.lead using opportunity_ids
    lead_fields = ['id', 'name', 'x_studio_oem_v2']  # Add any other fields you need
    leads = models.execute_kw(db, uid, password, 'crm.lead', 'search_read', [[['id', 'in', opportunity_ids]]],
                              {'fields': lead_fields})

    # Create a dictionary to map opportunity_id to lead details
    lead_dict = {lead['id']: lead for lead in leads}

    # Fetch additional fields from res.partner using partner_ids
    partner_fields = ['id', 'name', 'x_studio_oem']  # Add any other fields you need
    partners = models.execute_kw(db, uid, password, 'res.partner', 'search_read', [[['id', 'in', partner_ids]]],
                                 {'fields': partner_fields})

    # Create a dictionary to map partner_id to partner details
    partner_dict = {partner['id']: partner for partner in partners}

    # Fetch additional fields from mail.activity using activity_ids
    activity_fields = ['id', 'user_id', 'note', 'create_date', 'summary']  # Add any other fields you need
    activities = models.execute_kw(db, uid, password, 'mail.activity', 'search_read', [[['id', 'in', activity_ids]]],
                                   {'fields': activity_fields})

    # Create a dictionary to map activity_id to activity details
    activity_dict = {activity['id']: activity for activity in activities}

    # Add lead, partner, and activity details to orders
    for order in orders:
        # Lead Details
        if order['opportunity_id']:
            lead_id = order['opportunity_id'][0]
            lead_details = lead_dict.get(lead_id, {})
            order['lead_name'] = lead_details.get('name', '')
            order['lead_x_studio_oem'] = lead_details.get('x_studio_oem_v2', '')
        else:
            order['lead_name'] = ''
            order['lead_x_studio_oem'] = ''

        # Partner Details
        if order['partner_id']:
            partner_id = order['partner_id'][0]
            partner_details = partner_dict.get(partner_id, {})
            order['partner_name'] = partner_details.get('name', '')
            order['partner_x_studio_oem'] = partner_details.get('x_studio_oem', '')
        else:
            order['partner_name'] = ''
            order['partner_x_studio_oem'] = ''

        # Activity Details
        if order['activity_ids']:
            activity_users, activity_notes, activity_create_dates, activity_summaries = gather_activity_details(
                order['activity_ids'], activity_dict
            )
            order['activity_users'] = ', '.join(activity_users)
            order['activity_notes'] = ', '.join(activity_notes)
            order['activity_create_dates'] = ', '.join(activity_create_dates)
            order['activity_summaries'] = ', '.join(activity_summaries)
        else:
            order['activity_users'] = ''
            order['activity_notes'] = ''
            order['activity_create_dates'] = ''
            order['activity_summaries'] = ''

    # Convert to DataFrame
    df = pd.DataFrame(orders)

    # Export to Excel
    df.to_excel('SalesModule.xlsx', index=False)
    print("Data successfully exported to SalesModule.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")