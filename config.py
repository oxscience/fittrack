import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'fittrack-dev-key-change-in-production')
PORT = int(os.environ.get('FITTRACK_PORT', 5003))
HOST = os.environ.get('FITTRACK_HOST', '127.0.0.1')
DATABASE = os.path.join(BASE_DIR, os.environ.get('FITTRACK_DB', 'fittrack.db'))
