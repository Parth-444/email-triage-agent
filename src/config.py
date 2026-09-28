import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.6-flash")
MODEL_NAME = "gemini-3.6-flash"
JEV_API = os.getenv("jev_api")
TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY") or JEV_API
# JEV_MODEL_NAME = os.getenv("JEV_MODEL_NAME", "jev-latest")
JEV_MODEL_NAME = "jev-latest"

if JEV_API and not os.getenv("TYPESAFE_API_KEY"):
    os.environ["TYPESAFE_API_KEY"] = JEV_API


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=GOOGLE_API_KEY)

# Paths
DATA_DIR = "data"
SKILLS_DIR = "skills"
EMAILS_PATH = f"{DATA_DIR}/emails.json"
ORDERS_PATH = f"{DATA_DIR}/orders.json"
PRODUCTS_PATH = f"{DATA_DIR}/products.json"
POLICIES_DIR = f"{DATA_DIR}/policies"
