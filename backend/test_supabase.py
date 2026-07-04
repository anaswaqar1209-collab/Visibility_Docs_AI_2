import httpx, io
from PIL import Image

c = httpx.Client(base_url="http://localhost:8000", timeout=120)

# Upload
img = Image.new('RGB', (100, 30), color='white')
buf = io.BytesIO()
img.save(buf, format='PNG')
buf.seek(0)

r = c.post("/api/v1/documents/upload",
    data={"organization_id": "test-org"},
    files={"file": ("test.png", buf.getvalue(), "image/png")})
print(f"Upload: {r.status_code}", r.json())
doc_id = r.json().get("id", "")

# Process
if doc_id:
    r = c.post(f"/api/v1/documents/{doc_id}/process?organization_id=test-org")
    print(f"Process: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Status: {data['status']}")
        print(f"  Type: {data.get('classification', {}).get('document_type')}")
    else:
        print(f"  Error: {r.json().get('detail', '')[:300]}")

# List
r = c.get("/api/v1/documents", params={"organization_id": "test-org"})
print(f"List: {r.status_code} - {len(r.json().get('documents', []))} docs")

c.close()
