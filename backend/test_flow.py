import httpx, asyncio, io
from PIL import Image

async def test():
    c = httpx.AsyncClient()
    img = Image.new('RGB', (100, 30), color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    r = await c.post('http://localhost:8000/api/v1/documents/upload',
        data={'organization_id': 'test-org'},
        files={'file': ('test.png', buf.getvalue(), 'image/png')})
    print(f'Upload: {r.status_code}', r.json())
    doc_id = r.json().get('id', '')

    if doc_id:
        r = await c.post(f'http://localhost:8000/api/v1/documents/{doc_id}/process?organization_id=test-org')
        data = r.json()
        print(f'Process: {r.status_code}')
        if r.status_code >= 400:
            print(f'  Error: {data.get("detail", str(data))[:300]}')
        else:
            print(f'  Type: {data.get("classification", {}).get("document_type")}')

    await c.aclose()

asyncio.run(test())
