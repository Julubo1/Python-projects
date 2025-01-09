import pandas as pd
from bs4 import BeautifulSoup

# Load the Excel file
file_path = 'Message.xlsx'
df = pd.read_excel(file_path)

# Print the original column names
print("Original Column Names:")
print(df.columns)

# Function to strip HTML tags and leading/trailing whitespace
def strip_html_tags(text):
    if isinstance(text, str):
        soup = BeautifulSoup(text, 'html.parser')
        cleaned_text = soup.get_text()
        return cleaned_text.strip()  # Strip leading and trailing whitespace
    return text

# Apply the function to the column with HTML data (assuming it's named 'Contents')
# Adjust the column name based on the actual column names in your Excel file
df['Cleaned_Data'] = df['Contents'].apply(strip_html_tags)

# Save the cleaned data to a new Excel file
output_file_path = 'Message_cleaned.xlsx'
df.to_excel(output_file_path, index=False)

print(f"Cleaned data saved to {output_file_path}")