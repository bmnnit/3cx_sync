import sys
import csv
import json
import argparse
import psycopg2

BATCH = 1000

def fetch_rows(conn):
    with conn.cursor() as cur:
        cur.execute("""
            select
              idphonebook,
              firstname,
              lastname,
              phonenumber,
              company,
              tag,
              fkiddn,
              fkidtenant
            from public.phonebook
            order by idphonebook
        """)
        while True:
            rows = cur.fetchmany(BATCH)
            if not rows:
                break
            for r in rows:
                yield {
                    "idphonebook": r[0],
                    "firstname": r[1],
                    "lastname": r[2],
                    "phonenumber": r[3],
                    "company": r[4],
                    "tag": r[5],
                    "fkiddn": r[6],
                    "fkidtenant": r[7],
                }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["tsv","csv","ndjson"], default="tsv")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    conn = psycopg2.connect(host="/var/run/postgresql", dbname="database_single", user="postgres")
    conn.set_session(readonly=True, autocommit=False)

    rows = fetch_rows(conn)

    out = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8", newline="")
    try:
        if args.format in ("csv","tsv"):
            delim = "," if args.format == "csv" else "\t"
            fieldnames = ["idphonebook","firstname","lastname","phonenumber","company","tag","fkiddn","fkidtenant"]
            writer = csv.DictWriter(out, fieldnames=fieldnames, delimiter=delim)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: ("" if v is None else v) for k,v in row.items()})
        else:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
    finally:
        if out is not sys.stdout:
            out.close()
        conn.close()

if __name__ == "__main__":
    main()

