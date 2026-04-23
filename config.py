import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = {
    "host":os.getenv("host"),
    "port": os.getenv("port"),
    "user": os.getenv("user"),
    "password": os.getenv("password"),
    "database": os.getenv("database")
}
SECRET_KEY = os.getenv("SECRET_KEY") 