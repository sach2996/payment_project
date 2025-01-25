import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.INFO)  # Log info-level messages and above

if __name__ == '__main__':
    port = 5000  # You can set this dynamically if needed
    app.run(debug=True, host='0.0.0.0', port=port)

    # Log the port being used
    logging.info(f"Flask app is running on port {port}")
