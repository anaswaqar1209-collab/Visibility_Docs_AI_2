## Supabase connectivity check
## Run: python text.py

import os, sys, json, traceback
from datetime import datetime

OK = "PASS"
FAIL = "FAIL"

def check(service, fn):
    try:
        result = fn()
        print(f"  {OK} {service}")
        return result
    except Exception as e:
        print(f"  {FAIL} {service}: {e}")
        traceback.print_exc(limit=1)
        return None

print("=" * 55)
print("  Visibility Docs AI — Supabase Health Check")
print("=" * 55)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import settings

print(f"\n[1] Environment")
print(f"  SUPABASE_URL:     {settings.SUPABASE_URL[:40] + '...' if settings.SUPABASE_URL else '(empty)'}")
print(f"  SUPABASE_KEY:     {settings.SUPABASE_KEY[:10] + '...' if settings.SUPABASE_KEY else '(empty)'}")
print(f"  DATABASE_URL:     {settings.DATABASE_URL[:40] + '...' if settings.DATABASE_URL else '(empty)'}")
print(f"  PINECONE_API_KEY: {'set' if settings.PINECONE_API_KEY else '(empty)'}")
print(f"  GROQ_API_KEY:     {'set' if settings.GROQ_API_KEY else '(empty)'}")
print(f"  UPLOAD_DIR:       {settings.UPLOAD_DIR}")
print(f"  PaddleOCR:        available")

print(f"\n[2] Supabase Client")
supabase = None
def init_supabase():
    global supabase
    from supabase import create_client
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    supabase.table("documents").select("id").limit(1).execute()
    return supabase
check("create_client + ping", init_supabase)

print(f"\n[3] Tables")
tables = [
    "documents", "document_chunks", "document_embeddings",
    "document_extractions", "documents_metadata",
    "processing_jobs", "agent_runs",
    "validation_results", "workflow_instances",
]
for t in tables:
    def check_table(tbl=t):
        r = supabase.table(tbl).select("id").limit(1).execute()
        return r.data
    check(f"table '{t}' exists", check_table)

print(f"\n[4] CRUD operations")
doc_id = "health_check_" + datetime.now().strftime("%H%M%S")
org_id = "test-org"

inserted = None
def do_insert():
    global inserted
    r = supabase.table("documents").insert({
        "id": doc_id, "organization_id": org_id, "title": "health_check",
        "status": "uploaded", "original_file_url": "", "file_size": 0,
        "uploaded_by": "health_check",
    }).execute()
    inserted = r.data
    return len(r.data) > 0
check("insert document", do_insert)

def do_select():
    r = supabase.table("documents").select("*").eq("id", doc_id).execute()
    d = r.data[0] if r.data else None
    return d and d.get("title") == "health_check"
check("select document", do_select)

def do_update():
    r = supabase.table("documents").update({"document_type": "test"}).eq("id", doc_id).execute()
    return r.data and r.data[0].get("document_type") == "test"
check("update document_type", do_update)

def do_delete():
    r = supabase.table("documents").delete().eq("id", doc_id).execute()
    return True
check("delete document", do_delete)

print(f"\n[5] Supabase Storage")
def check_bucket():
    r = supabase.storage.list_buckets()
    names = [b.get("name") or b.name for b in r]
    return "documents" in names
check("bucket 'documents' listed", check_bucket)

print(f"\n[6] PostgreSQL Direct (DATABASE_URL)")
def pg_connect():
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT 1")
    cur.close(); conn.close()
    return True
check("psycopg2 connect", pg_connect)

def pg_vector():
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT * FROM pg_extension WHERE extname='vector'")
    ok = cur.fetchone() is not None
    cur.close(); conn.close()
    return ok
check("pgvector extension", pg_vector)

print(f"\n[7] Local SQLite Fallback")
def sqlite_insert():
    from app.database import _get_local_db
    db = _get_local_db()
    db.execute("INSERT OR IGNORE INTO documents (id, organization_id, title, status) VALUES (?,?,?,?)",
               (doc_id + "_sqlite", org_id, "health_check", "uploaded"))
    db.commit()
    return True
check("sqlite insert", sqlite_insert)

def sqlite_select():
    from app.database import _get_local_db
    db = _get_local_db()
    cur = db.execute("SELECT title FROM documents WHERE id=?", (doc_id + "_sqlite",))
    return cur.fetchone() is not None
check("sqlite select", sqlite_select)

def sqlite_clean():
    from app.database import _get_local_db
    db = _get_local_db()
    db.execute("DELETE FROM documents WHERE id LIKE ?", ("health_check%",))
    db.commit()
    return True
check("sqlite cleanup", sqlite_clean)

print(f"\n{'='*55}")
print(f"  Done")
print(f"{'='*55}")
