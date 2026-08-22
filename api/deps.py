import os
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

def get_groq_api_key():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in .env file")
    return api_key