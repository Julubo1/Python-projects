import xmlrpc.client
import pandas as pd
import re

# Function to remove HTML tags
def remove_html_tags(text):
    if text is None:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# Function to extract IDs from a string like [1234] or [1234, 5435]
def extract_ids(oem_str):
    # Use regular expression to find all numbers in the string
    ids = re.findall(r'\d+', oem_str)
    # Join the IDs with a comma and space
    return ', '.join(ids)


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

    # Set the language context
    context = {'lang': 'en_GB'}  # Change 'en_US' to your desired language code

    # Fetch CRM Lead records
    leads = models.execute_kw(db, uid, password, 'crm.lead', 'search_read', [[]], {
        'fields': [
            'id',
            'name',
            'contact_name',
            'date_deadline',
            'expected_revenue',
            'activity_ids',
            'activity_date_deadline',
            'activity_summary',
            'x_studio_oem_v2',
            'partner_id',
            'x_studio_forecast',
            'team_id',
            'company_id',
            'x_studio_slagingskans',
            'email_from',
            'stage_id',
            'tag_ids',
            'date_closed',
            'x_studio_sd_quote',
            'x_studio_rd_po_c',
            'x_studio_po_c_reference',
            'x_studio_dl_itt_peo_c',
            'x_studio_rd_itt_c_peo',
            'x_studio_expected_delivery',
            'x_studio_result_responsable',
            'create_date',
            'quotation_count',
        ],
        'context': context
    })

    # Extract partner_ids and activity_ids
    partner_ids = [lead['partner_id'][0] for lead in leads if lead['partner_id']]
    activity_ids = [activity_id for lead in leads for activity_id in lead['activity_ids']]

    # Fetch additional fields from res.partner using partner_ids
    partner_fields = ['id', 'name', 'x_studio_oem']  # Add any other fields you need
    partners = models.execute_kw(db, uid, password, 'res.partner', 'search_read', [[['id', 'in', partner_ids]]],
                                 {'fields': partner_fields, 'context': context})

    # Create a dictionary to map partner_id to partner details
    partner_dict = {partner['id']: partner for partner in partners}

    # Fetch additional fields from mail.activity using activity_ids
    activity_fields = ['id', 'user_id', 'note', 'create_date']  # Add any other fields you need
    activities = models.execute_kw(db, uid, password, 'mail.activity', 'search_read', [[['id', 'in', activity_ids]]],
                                   {'fields': activity_fields, 'context': context})

    # Create a dictionary to map activity_id to activity details
    activity_dict = {activity['id']: activity for activity in activities}

    # Fetch CRM Team Names
    team_ids = [lead['team_id'][0] for lead in leads if lead['team_id']]
    team_fields = ['id', 'name']  # Add any other fields you need
    teams = models.execute_kw(db, uid, password, 'crm.team', 'search_read', [[['id', 'in', team_ids]]],
                              {'fields': team_fields, 'context': context})

    # Create a dictionary to map team_id to team name
    team_dict = {team['id']: team['name'] for team in teams}

    # Fetch CRM Stage Names
    stage_ids = [lead['stage_id'][0] for lead in leads if lead['stage_id']]
    stage_fields = ['id', 'name']  # Add any other fields you need
    stages = models.execute_kw(db, uid, password, 'crm.stage', 'search_read', [[['id', 'in', stage_ids]]],
                               {'fields': stage_fields, 'context': context})

    # Create a dictionary to map stage_id to stage name
    stage_dict = {stage['id']: stage['name'] for stage in stages}

    # Add partner, activity, and oem details to leads
    for lead in leads:
        if lead['partner_id']:
            partner_id = lead['partner_id'][0]
            partner_details = partner_dict.get(partner_id, {})
            lead['partner_name'] = partner_details.get('name', '')
            lead['partner_x_studio_oem'] = partner_details.get('x_studio_oem', '')

        if lead['activity_ids']:
            activity_users = []
            activity_notes = []
            activity_create_dates = []
            for activity_id in lead['activity_ids']:
                activity_details = activity_dict.get(activity_id, {})
                user_id = activity_details.get('user_id', [0, ''])[1]  # Get the user name
                activity_users.append(user_id)
                note = activity_details.get('note', '')
                clean_note = remove_html_tags(note)  # Remove HTML tags
                activity_notes.append(clean_note)
                activity_create_dates.append(activity_details.get('create_date', ''))
            lead['activity_users'] = ', '.join(activity_users)
            lead['activity_notes'] = ', '.join(activity_notes)
            lead['activity_create_dates'] = ', '.join(activity_create_dates)
        else:
            lead['activity_users'] = ''
            lead['activity_notes'] = ''
            lead['activity_create_dates'] = ''

        # Map team_id to team name
        if lead['team_id']:
            lead['team_name'] = team_dict.get(lead['team_id'][0], '')

        # Map stage_id to stage name
        if lead['stage_id']:
            lead['stage_name'] = stage_dict.get(lead['stage_id'][0], '')

        # Extract OEM IDs and convert to a clean string
        if lead['x_studio_oem_v2']:
            lead['x_studio_oem_v2_ids'] = extract_ids(str(lead['x_studio_oem_v2']))
        else:
            lead['x_studio_oem_v2_ids'] = ''

    # Convert to DataFrame
    df = pd.DataFrame(leads)

    # Debugging: Print the first few leads to verify the data
    print(df.head())

    # Export to Excel
    df.to_excel('CRM.xlsx', index=False)
    print("Data successfully exported to CRM.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")