from supabase import create_client
url = "https://bwaozsyexbqwinhwgxwi.supabase.co"
key = "sb_publishable_8VeiAnUTgPWwVzGyuk7xvA_syr6cMR5"
client = create_client(url, key)
try:
    result = client.table("documents").select("id").limit(1).execute()
    print("Supabase REST OK:", result)
except Exception as e:
    print("Supabase REST FAILED:", e)
