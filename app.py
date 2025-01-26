from app import app
import os
from dotenv import load_dotenv

load_dotenv()

PORT = os.getenv("PORT")
if __name__ == '__main__':
    app.run(debug=True, port=PORT)