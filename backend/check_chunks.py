import sqlite3, os
from supabase import create_client

# check local
db_path = os.path.join(os.path.dirname(__file__), "docs_ai.db")
conn = sqlite3.connect(db_path)
rows = conn.execute("SELECT document_id, content FROM document_chunks LIMIT 5").fetchall()
print(f"Local chunks: {len(rows)}")
for r in rows[:2]:
    print(f"  Doc: {r[0]}, Content: {str(r[1])[:100]}")

# check Supabase
client = create_client("https://bwaozsyexbqwinhwgxwi.supabase.co", "sb_publishable_8VeiAnUTgPWwVzGyuk7xvA_syr6cMR5")
r = client.table("document_chunks").select("document_id, content").limit(5).execute()
print(f"Supabase chunks: {len(r.data)}")
for d in r.data[:2]:
    print(f"  Doc: {d['document_id']}, Content: {str(d.get('content',''))[:100]}")

r = client.table("document_embeddings").select("document_id").limit(5).execute()
print(f"Supabase embeddings: {len(r.data)}")
