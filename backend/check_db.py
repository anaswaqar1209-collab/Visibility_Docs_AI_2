import psycopg2
conn = psycopg2.connect('postgresql://postgres.bwaozsyexbqwinhwgxwi:Anaswaqar123@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres')
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)
cur.execute("SELECT * FROM pg_extension WHERE extname='vector'")
vec = cur.fetchall()
print('pgvector:', 'enabled' if vec else 'NOT enabled')
cur.close()
conn.close()
