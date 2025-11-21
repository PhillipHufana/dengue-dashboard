from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # or anon key for testing

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
