"""
Checks whether dw (Redshift) has an equivalent parents/advisor path,
so we can drop the MySQL dependency entirely and get advisor info the
same safe way as everything else in this app.
"""
import psycopg2, os, pandas as pd

conn = psycopg2.connect(
    host='redshift.revolutionprep.com', port=5439, dbname='rp_admin',
    user='tharrington', password=os.environ['REDSHIFT_PASSWORD'], connect_timeout=10
)

print("=== Does dw.parents exist? ===")
try:
    df1 = pd.read_sql("SELECT column_name FROM information_schema.columns WHERE table_schema='dw' AND table_name='parents'", conn)
    print(df1.to_string())
except Exception as e:
    print(f"Error: {e}")

print("\n=== Does dw.students have advisor info directly? ===")
try:
    df2 = pd.read_sql("SELECT column_name FROM information_schema.columns WHERE table_schema='dw' AND table_name='students'", conn)
    print(df2.to_string())
except Exception as e:
    print(f"Error: {e}")

print("\n=== Any dw table/column with 'advisor' in the name? ===")
try:
    df3 = pd.read_sql("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='dw' AND column_name ILIKE '%advisor%'", conn)
    print(df3.to_string())
except Exception as e:
    print(f"Error: {e}")

conn.close()
