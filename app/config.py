import os
import certifi

class Config:
    MONGO_URI = os.getenv("MONGO_URI")  + certifi.where()  # Load from environment variable
    UPLOAD_FOLDER = './uploads'          # Directory for file uploads
