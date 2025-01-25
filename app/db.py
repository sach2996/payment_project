# db.py
from pymongo import MongoClient
import certifi
import os
from dotenv import load_dotenv
from gridfs import GridFS

# Load environment variables
load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI") + certifi.where()
client = MongoClient(MONGO_URI)
db = client["paymentProject"]
collection = db["payments"]  # The collection reference

# fs = db.gridfs  # Initialize GridFS

# Export collection and fs for use in other files
def get_collection():
    return collection

def get_fs():
    return GridFS(db)
