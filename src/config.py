import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite-preview")


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=GOOGLE_API_KEY)

# Paths
DATA_DIR = "data"
SKILLS_DIR = "skills"
EMAILS_PATH = f"{DATA_DIR}/emails.json"
ORDERS_PATH = f"{DATA_DIR}/orders.json"
PRODUCTS_PATH = f"{DATA_DIR}/products.json"
POLICIES_DIR = f"{DATA_DIR}/policies"
