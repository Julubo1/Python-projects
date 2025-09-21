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

    # Fetch available fields for product.template to verify
    fields = models.execute_kw(db, uid, password, 'product.template', 'fields_get', [])

    # Define the fields you need for product.template
    product_fields = [
        'name',
        'default_code',
        'categ_id',
        'detailed_type',
        'uom_id',
        'x_studio_supplier',
        'sales_count',
        'x_studio_sales_order_lines',
    ]

    # Filter out fields that are not available in the product.template model
    available_product_fields = [field for field in product_fields if field in fields]

    # Fetch product.template records
    products = models.execute_kw(db, uid, password, 'product.template', 'search_read', [[]], {
        'fields': available_product_fields
    })
    print(f"Fetched {len(products)} Product records.")

    # Prepare a list to store all product data
    all_product_data = []

    # Fetch sales order lines for each product
    for product in products:
        # Get the IDs of the related sale.order.line records
        line_ids = product.get('x_studio_sales_order_lines', [])

        # Ensure line_ids is a list
        #if not isinstance(line_ids, list):
            #print(f"Warning: x_studio_sales_order_lines for product {product['name']} is not a list: {line_ids}")
            #continue

        # Fetch available fields for sale.order.line to verify
        line_fields = models.execute_kw(db, uid, password, 'sale.order.line', 'fields_get', [])

        # Define the fields you need for sale.order.line
        line_required_fields = [
            'x_studio_date',  # Ensure this field exists in sale.order.line
            'product_uom_qty',
            'price_unit',
        ]

        # Filter out fields that are not available in the sale.order.line model
        available_line_fields = [field for field in line_required_fields if field in line_fields]

        # Construct a domain to fetch the sale.order.line records
        domain = [('id', 'in', line_ids)]

        # Fetch sale.order.line records
        lines = models.execute_kw(db, uid, password, 'sale.order.line', 'search_read', [domain], {
            'fields': available_line_fields
        })



        # Merge product data with its sales order lines
        for line in lines:
            product_data = product.copy()
            product_data.update(line)
            all_product_data.append(product_data)

    # Convert to DataFrame
    df = pd.DataFrame(all_product_data)

    # Remove HTML tags from the 'note' column if it exists
    if 'note' in df.columns:
        df['note'] = df['note'].apply(remove_html_tags)

    # Export to Excel
    df.to_excel('Products.xlsx', index=False)
    print("Data successfully exported to Products.xlsx.")

except Exception as e:
    print(f"An error occurred: {e}")