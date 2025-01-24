import gridfs
from app import mongo, fs
import pandas as pd
from datetime import datetime

# Function to normalize CSV data and save to MongoDB
def normalize_csv_and_store(file_path):
    try:
        # Read CSV file
        df = pd.read_csv(file_path)

        # Normalize fields and add calculated fields
        df['payee_due_date'] = pd.to_datetime(df['payee_due_date'], errors='coerce').dt.strftime('%Y-%m-%d')

        # Add payment status and total_due
        today = datetime.today().date()
        df['payee_payment_status'] = df['payee_due_date'].apply(
            lambda x: 'due_now' if datetime.strptime(x, '%Y-%m-%d').date() == today
            else 'overdue' if datetime.strptime(x, '%Y-%m-%d').date() < today
            else 'pending'
        )

        df['total_due'] = df['due_amount'] - df['discount_percent'] + df['tax_percent']

        # Convert DataFrame to dictionary for MongoDB insertion
        data_to_insert = df.to_dict(orient='records')

        # Insert into MongoDB
        mongo.db.payments.insert_many(data_to_insert)
        print(f"Successfully inserted {len(data_to_insert)} records into MongoDB.")

    except Exception as e:
        print(f"Error: {e}")

# Helper function to check allowed file types
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
