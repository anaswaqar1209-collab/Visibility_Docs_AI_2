from supabase import create_client
import uuid, datetime
client = create_client("https://bwaozsyexbqwinhwgxwi.supabase.co", "sb_publishable_8VeiAnUTgPWwVzGyuk7xvA_syr6cMR5")
now = datetime.datetime.utcnow().isoformat()
doc_id = uuid.uuid4().hex
data = {"id": doc_id, "organization_id": "test-org", "title": "test.png", "status": "uploaded", "created_at": now, "updated_at": now}
try:
    r = client.table("documents").insert(data).execute()
    print("Insert OK:", r.data)
except Exception as e:
    print("Insert error:", e)
try:
    r = client.table("documents").select("*").execute()
    print("All docs:", r.data)
except Exception as e:
    print("Select error:", e)
