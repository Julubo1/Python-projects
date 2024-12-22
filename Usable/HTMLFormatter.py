# Cleaning/deleting HTML Tags from a desired Excel Column and put the result in a new column. Line 29 for the desired column
import pandas as pd
from bs4 import BeautifulSoup

# Load the Excel file
file_path = 'Contacts.xlsx'
df = pd.read_excel(file_path)

# Print the original column names
print("Original Column Names:")
print(df.columns)

# Strip leading and trailing whitespace and any special characters
df.columns = df.columns.str.strip().str.replace('[^\w\s]', '', regex=True)

# Print the cleaned column names
print("\nCleaned Column Names:")
print(df.columns)

# Function to strip HTML tags
def strip_html_tags(text):
    if isinstance(text, str):
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text()
    return text

# Apply the function to the column with HTML data (assuming it's named 'next activity note')
# Adjust the column name based on the cleaned column names
df['Cleaned_Data'] = df['ActivitiesNote'].apply(strip_html_tags)

# Save the cleaned data to a new Excel file
output_file_path = 'Contacts_cleaned.xlsx'
df.to_excel(output_file_path, index=False)

print(f"Cleaned data saved to {output_file_path}")
