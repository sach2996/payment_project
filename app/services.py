import gridfs
from app import mongo, fs
import pandas as pd
from datetime import datetime

# Function to normalize CSV data and save to MongoDB
def normalize_csv_and_store(file_path):
    try:
        # Read CSV file
        df = pd.read_csv(file_path)

        # Ensure all columns exist in the dataframe
        required_columns = [
            'payee_first_name', 'payee_last_name', 'payee_payment_status', 
            'payee_added_date_utc', 'payee_due_date', 'payee_address_line_1', 
            'payee_address_line_2', 'payee_city', 'payee_country', 'payee_province_or_state', 
            'payee_postal_code', 'payee_phone_number', 'payee_email', 'currency', 
            'discount_percent', 'tax_percent', 'due_amount'
        ]
        
        # Ensure that all required columns are present in the CSV
        for col in required_columns:
            if col not in df.columns:
                df[col] = None  # Adding missing columns with None

        # Normalize 'payee_due_date' and ensure correct format
        df['payee_due_date'] = pd.to_datetime(df['payee_due_date'], errors='coerce').dt.strftime('%Y-%m-%d')

        # Add payment status based on 'payee_due_date'
        today = datetime.today().date()
        df['payee_payment_status'] = df['payee_due_date'].apply(
            lambda x: 'due_now' if datetime.strptime(x, '%Y-%m-%d').date() == today
            else 'overdue' if datetime.strptime(x, '%Y-%m-%d').date() < today
            else 'pending'
        )

        # Add 'payee_added_date_utc' to the DataFrame if missing (assumed current time)
        df['payee_added_date_utc'] = pd.to_datetime(df['payee_added_date_utc'], errors='coerce')
        if df['payee_added_date_utc'].isnull().any():
            df['payee_added_date_utc'] = pd.to_datetime(today)

        # Add calculated fields 'total_due'
        df['total_due'] = df['due_amount'] - df['discount_percent'].fillna(0) + df['tax_percent'].fillna(0)

        # Convert the DataFrame to a dictionary for MongoDB insertion
        data_to_insert = df.to_dict(orient='records')

        mongo.db.payments.insert_many(data_to_insert)
        print(f"Successfully inserted {len(data_to_insert)} records into MongoDB.")

    except Exception as e:
        print(f"Error: {e}")

# Helper function to check allowed file types
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
