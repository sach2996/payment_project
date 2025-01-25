from flask import Flask
from flask_pymongo import PyMongo
from flask_cors import CORS, cross_origin
import gridfs
from dotenv import load_dotenv
import os
import certifi

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)

# MongoDB Configuration
app.config["MONGO_URI"] = os.getenv("MONGO_URI")  + certifi.where()
mongo = PyMongo(app)
fs = gridfs.GridFS(mongo.db)

# Enable CORS
CORS(app)

# Import routes after initializing the app
from app import routes

