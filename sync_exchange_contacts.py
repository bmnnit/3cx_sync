import os
import sys
import argparse
import psycopg
import phonenumbers
from exchangelib import Credentials, Account, Configuration, DELEGATE, ExtendedProperty
from exchangelib.folders import Contacts
from exchangelib.items import Contact
import re

from exchangelib.items import Contact
from exchangelib.indexed_properties import PhoneNumber, EmailAddress

def create_or_update(fld, rec, existing_map, do_update, phone_list, email_list):
    extid = str(rec["id"])
    fn = (rec.get("firstname") or "").strip() or None
    ln = (rec.get("lastname") or "").strip() or None
    company = (rec.get("company") or "").strip() or None
    display = " ".join(x for x in [fn, ln] if x).strip() or company or f"Contact {extid}"

    if extid in existing_map:
        if not do_update:
            return "exists"
        it = existing_map[extid]
        changed = False

        if it.display_name != display:
            it.display_name = display; changed = True
        if fn is not None and it.given_name != fn:
            it.given_name = fn; changed = True
        if ln is not None and it.surname != ln:
            it.surname = ln; changed = True
        if company != it.company_name:
            it.company_name = company; changed = True

        if phone_list:
            cur = list(it.phone_numbers or [])
            by_label = {p.label: p.phone_number for p in cur}
            for p in phone_list:
                if by_label.get(p.label) != p.phone_number:
                    by_label[p.label] = p.phone_number
                    changed = True
            ordered = []
            for lbl in ("BusinessPhone","MobilePhone","HomePhone","CompanyMainPhone","BusinessPhone2","OtherTelephone"):
                if lbl in by_label:
                    ordered.append(PhoneNumber(label=lbl, phone_number=by_label[lbl]))
            for lbl, num in by_label.items():
                if lbl not in {x.label for x in ordered}:
                    ordered.append(PhoneNumber(label=lbl, phone_number=num))
            if cur != ordered:
                it.phone_numbers = ordered
                changed = True

        if email_list:
            cur = list(it.email_addresses or [])
            by_label = {e.label: e.email for e in cur}
            for e in email_list:
                if by_label.get(e.label) != e.email:
                    by_label[e.label] = e.email
                    changed = True
            ordered = []
            for lbl in ("EmailAddress1","EmailAddress2","EmailAddress3"):
                if lbl in by_label:
                    ordered.append(EmailAddress(label=lbl, email=by_label[lbl]))
            for lbl, addr in by_label.items():
                if lbl not in {x.label for x in ordered}:
                    ordered.append(EmailAddress(label=lbl, email=addr))
            if cur != ordered:
                it.email_addresses = ordered
                changed = True

        if changed:
            it.save()
            return "updated"
        return "unchanged"

    c = Contact(
        folder=fld,
        given_name=fn,
        surname=ln,
        company_name=company,
        display_name=display,
        categories=["3CX Phonebook"] if rec.get("tag") else None,
        phonebook_id=extid,
    )
    c.save()

    changed = False
    if phone_list:
        c.phone_numbers = phone_list; changed = True
    if email_list:
        c.email_addresses = email_list; changed = True
    if changed:
        c.save()
    return "created"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DB_DSN = "host=/var/run/postgresql dbname=database_single user=postgres"

EXCH_EMAIL = os.environ.get("EXCH_EMAIL")
EXCH_USER = os.environ.get("EXCH_USER")
EXCH_PASS = os.environ.get("EXCH_PASS")
EXCH_SERVER = os.environ.get("EXCH_SERVER")
EXCH_FOLDER = os.environ.get("EXCH_FOLDER", "Phonebook")
EXCH_AUTODISCOVER = os.environ.get("EXCH_AUTODISCOVER", "false").lower() in ("1","true","yes")

class PhonebookIdProp(ExtendedProperty):
    distinguished_property_set_id = 'PublicStrings'
    property_name = 'PhonebookId'
    property_type = 'String'

Contact.register('phonebook_id', PhonebookIdProp)

def norm_all(*vals):
    out = []
    seen = set()
    for v in vals:
        if not v:
            continue
        n = norm_phone(str(v))
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def build_phone_list(rec, primary="business"):
    b = norm_phone(rec.get("phone_business"))
    m = norm_phone(rec.get("phone_mobile"))
    h = norm_phone(rec.get("phone_home"))
    out = []
    if primary == "business":
        if b: out.append(PhoneNumber(label="BusinessPhone", phone_number=b))
        if m and m != b: out.append(PhoneNumber(label="MobilePhone", phone_number=m))
        if h and h not in (b, m): out.append(PhoneNumber(label="HomePhone", phone_number=h))
    else:
        if m: out.append(PhoneNumber(label="MobilePhone", phone_number=m))
        if b and b != m: out.append(PhoneNumber(label="BusinessPhone", phone_number=b))
        if h and h not in (b, m): out.append(PhoneNumber(label="HomePhone", phone_number=h))
    return out

def build_email_list(rec):
    def norm_email(x):
        x = (x or "").strip().lower()
        return x if ("@" in x and "." in x) else None
    e1 = norm_email(rec.get("email1"))
    e2 = norm_email(rec.get("email2"))
    out = []
    if e1: out.append(EmailAddress(label="EmailAddress1", email=e1))
    if e2 and e2 != e1: out.append(EmailAddress(label="EmailAddress2", email=e2))
    return out

def build_phone_map(rec):
    phones = {}
    b = norm_phone(rec.get("phone_business"))
    m = norm_phone(rec.get("phone_mobile"))
    h = norm_phone(rec.get("phone_home"))
    if b: phones["BusinessPhone"] = b
    if m and m != b: phones["MobilePhone"] = m
    if h and h not in (b, m): phones["HomePhone"] = h
    return phones

def build_email_map(rec):
    def norm_email(x):
        x = (x or "").strip()
        return x.lower() if EMAIL_RE.match(x) else None
    e1 = norm_email(rec.get("email1"))
    e2 = norm_email(rec.get("email2"))
    emails = {}
    if e1: emails["EmailAddress1"] = e1
    if e2 and e2 != e1: emails["EmailAddress2"] = e2
    return emails

PHONE_VAL = re.compile(r"^[+0-9() .-]{5,}$")

def norm_phone(s):
    if not s:
        return None
    s = str(s).strip()
    if not PHONE_VAL.match(s):
        return None
    try:
        import phonenumbers
        n = phonenumbers.parse(s, None)
        if not phonenumbers.is_possible_number(n):
            return s
        return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        return s

def rows_from_db():
    with psycopg.connect(DB_DSN) as conn:
        conn.execute("set default_transaction_read_only = on")
        with conn.cursor() as cur:
            cur.execute("""
                select
                  idphonebook,
                  firstname,
                  lastname,
                  phonenumber,   -- -> BusinessPhone
                  company,
                  tag,
                  fkiddn,
                  fkidtenant,
                  pv_an3,        -- -> MobilePhone
                  pv_an1,        -- -> HomePhone
                  pv_an5,        -- -> EmailAddress1
                  pv_an6         -- -> EmailAddress2
                from public.phonebook
                order by idphonebook
            """)
            for r in cur:
                yield {
                    "id": r[0],
                    "firstname": r[1] or "",
                    "lastname": r[2] or "",
                    "phone_business": r[3] or "",
                    "company": r[4] or "",
                    "tag": r[5] or "",
                    "fkiddn": r[6],
                    "fkidtenant": r[7],
                    "phone_mobile": r[8] or "",
                    "phone_home": r[9] or "",
                    "email1": r[10] or "",
                    "email2": r[11] or "",
                }

def build_phone_map(rec, primary="business"):
    b = norm_phone(rec.get("phone_business"))
    m = norm_phone(rec.get("phone_mobile"))
    h = norm_phone(rec.get("phone_home"))

    phones = {}
    if primary == "business":
        main = b or m or h
        if main: phones["BusinessPhone"] = main
        if m and m != phones.get("BusinessPhone"): phones["MobilePhone"] = m
        if h and h not in (phones.get("BusinessPhone"), phones.get("MobilePhone")): phones["HomePhone"] = h
    else:
        main = m or b or h
        if main: phones["MobilePhone"] = main
        if b and b != phones.get("MobilePhone"): phones["BusinessPhone"] = b
        if h and h not in (phones.get("MobilePhone"), phones.get("BusinessPhone")): phones["HomePhone"] = h
    return phones


def connect_exchange():
    if not (EXCH_EMAIL and EXCH_USER and EXCH_PASS):
        print("Missing EXCH_EMAIL, EXCH_USER, EXCH_PASS", file=sys.stderr)
        sys.exit(2)
    creds = Credentials(username=EXCH_USER, password=EXCH_PASS)
    if EXCH_AUTODISCOVER:
        acc = Account(primary_smtp_address=EXCH_EMAIL, credentials=creds, autodiscover=True, access_type=DELEGATE)
    else:
        if not EXCH_SERVER:
            print("Set EXCH_SERVER or enable EXCH_AUTODISCOVER", file=sys.stderr)
            sys.exit(2)
        cfg = Configuration(server=EXCH_SERVER, credentials=creds)
        acc = Account(primary_smtp_address=EXCH_EMAIL, config=cfg, autodiscover=False, access_type=DELEGATE)
    _ = acc.root.tree()
    return acc


def ensure_target_folder(acc):
    # Use the default Contacts folder if EXCH_FOLDER is empty or equals Contacts/Kontakte
    if not EXCH_FOLDER or EXCH_FOLDER.lower() in ("contacts", "kontakte"):
        return acc.contacts
    # Otherwise find or create the named subfolder under Contacts
    for f in acc.contacts.children:
        if isinstance(f, Contacts) and f.name == EXCH_FOLDER:
            return f
    fld = Contacts(parent=acc.contacts, name=EXCH_FOLDER)
    fld.save()
    return fld


def load_existing_by_extid(fld):
    existing = {}
    for item in fld.all().only("id", "changekey", "phonebook_id"):
        extid = getattr(item, "phonebook_id", None)
        if extid:
            existing[str(extid)] = item
    return existing









def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--primary", choices=["business", "mobile"], default="business")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    acc = connect_exchange()
    fld = ensure_target_folder(acc)
    existing = load_existing_by_extid(fld)

    created = updated = unchanged = skipped = 0
    processed = 0

    print(f"Syncing to folder: {fld.name}")
    print(f"Existing contacts in folder: {len(existing)}")
    print("------------------------------------------------------------")

    for rec in rows_from_db():
        if args.limit and processed >= args.limit:
            break
        processed += 1

        has_any_phone = any([
            rec.get("phone_business"),
            rec.get("phone_mobile"),
            rec.get("phone_home"),
        ])
        if not has_any_phone and not rec.get("firstname") and not rec.get("lastname") and not rec.get("company"):
            skipped += 1
            continue

        extid = str(rec["id"])
        name = (f"{rec.get('firstname','')} {rec.get('lastname','')}".strip()
                or rec.get("company", "") or f"Contact {extid}")

        phone_list = build_phone_list(rec, primary=args.primary)
        email_list = build_email_list(rec)
        preview = " ".join([p.phone_number for p in phone_list][:3])[:40]

        if args.dry_run:
            action = "CREATE" if extid not in existing else ("UPDATE" if args.update else "EXISTS")
            print(f"{processed:5d}: {action:8s}  {extid:6s}  {name:<30s}  {preview}")
            continue

        res = create_or_update(fld, rec, existing, args.update, phone_list, email_list)
        if res == "created":
            created += 1
        elif res == "updated":
            updated += 1
        elif res == "unchanged":
            unchanged += 1
        elif res == "exists":
            skipped += 1

        print(f"{processed:5d}: {res.upper():8s}  {extid:6s}  {name:<30s}  {preview}")

        if processed % 100 == 0:
            print(f"-- progress {processed} total "
                  f"({created} created, {updated} updated, {unchanged} unchanged, {skipped} skipped) --")

    print("------------------------------------------------------------")
    print(f"Done: {processed} processed, {created} created, {updated} updated, {unchanged} unchanged, {skipped} skipped")


if __name__ == "__main__":
    main()

