import csv
import os
import sys
import pandas as pd
from tkinter import filedialog

def datacleaner(input_file, output_file=None):
    try:
        if input_file.endswith('.csv'):
            df = pd.read_csv(input_file)
        elif input_file.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(input_file)
        else:
            print("Error: Unsupported file type.")
            sys.exit(1)

        cleaned_df = df[df.iloc[:, 0].apply(lambda x: str(x).isdigit())]

        output_file = os.path.join(os.path.dirname(input_file), f"cleaned_{os.path.splitext(os.path.basename(input_file))[0]}.csv")

        cleaned_df.to_csv(output_file, index=False)

        print(f"Cleaned file saved to: {os.path.abspath(output_file)}")
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
    except PermissionError:
        print(f"Error: Permission denied for file '{input_file}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    def main():
        input_file = filedialog.askopenfilename(title="Select CSV or Excel File", filetypes=[("CSV Files", "*.csv"), ("Excel Files", "*.xls *.xlsx")])
        if not input_file:
            print("No file selected. Exiting.")
            sys.exit(1)

        datacleaner(input_file)

    if os.environ.get('DISPLAY') is None and sys.platform.startswith('linux'):
        print("Error: No display available for Tkinter. Please run in a graphical environment.")
        sys.exit(1)
    main()
