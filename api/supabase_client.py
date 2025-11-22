# from supabase import create_client
# import os

# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # or anon key for testing

# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# api/supabase_client.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # service role for upsert and read

    if not url or not key:
        raise RuntimeError("Supabase credentials missing")

    return create_client(url, key)
