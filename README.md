# 3CX Phonebook Sync

A Python-based synchronization tool for syncing 3CX phonebook contacts with Microsoft Exchange Server.

## Overview

This project provides tools to export and synchronize contact information from a 3CX phone system's PostgreSQL database to Microsoft Exchange Server contacts. It includes two main scripts:

1. **sync_phonebook.py** - Export phonebook data to various formats
2. **sync_exchange_contacts.py** - Synchronize phonebook contacts to Exchange Server

## Features

- Export 3CX phonebook data in multiple formats (TSV, CSV, NDJSON)
- One-way sync from 3CX to Microsoft Exchange Server
- Automatic phone number normalization to E.164 international format
- Email address validation and formatting
- Support for multiple phone numbers per contact (Business, Mobile, Home)
- Support for multiple email addresses per contact
- Custom extended properties to track phonebook IDs in Exchange
- Batch processing for large contact lists
- Dry-run mode for testing
- Update existing contacts or create new ones
- Configurable folder management in Exchange

## Requirements

- Python 3.7+
- PostgreSQL database (3CX phone system database)
- Microsoft Exchange Server with EWS (Exchange Web Services) enabled
- Network access to both PostgreSQL and Exchange Server

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd 3cx_sync
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Configure the following environment variables for Exchange Server connection:

- `EXCH_EMAIL` - Your Exchange email address (required)
- `EXCH_USER` - Exchange username (usually same as email) (required)
- `EXCH_PASS` - Exchange password (required)
- `EXCH_SERVER` - Exchange server hostname (required if autodiscover is disabled)
- `EXCH_FOLDER` - Target folder name in Contacts (default: "Phonebook")
- `EXCH_AUTODISCOVER` - Enable Exchange autodiscover (default: "false")

### Database Connection

The scripts connect to PostgreSQL using:
- Host: `/var/run/postgresql` (Unix socket)
- Database: `database_single`
- User: `postgres`

Modify the `DB_DSN` variable in the scripts if your configuration differs.

### Configuration File

Copy and customize the template:
```bash
cp run.sh.template run.sh
chmod +x run.sh
```

Edit `run.sh` with your Exchange credentials and settings.

## Usage

### Export Phonebook Data

Export contacts to TSV format (default):
```bash
python sync_phonebook.py --out contacts.tsv
```

Export to CSV:
```bash
python sync_phonebook.py --format csv --out contacts.csv
```

Export to NDJSON (newline-delimited JSON):
```bash
python sync_phonebook.py --format ndjson --out contacts.ndjson
```

### Sync to Exchange Server

Basic sync (create new contacts only):
```bash
python sync_exchange_contacts.py
```

Sync with updates (update existing contacts):
```bash
python sync_exchange_contacts.py --update
```

Dry-run mode (preview changes without making them):
```bash
python sync_exchange_contacts.py --update --dry-run
```

Limit number of contacts to process:
```bash
python sync_exchange_contacts.py --limit 100
```

Set primary phone number preference:
```bash
python sync_exchange_contacts.py --primary mobile  # Default is "business"
```

### Using the Shell Script

After configuring `run.sh`:
```bash
./run.sh
```

## Scripts Description

### sync_phonebook.py

Exports phonebook data from the PostgreSQL database to various formats.

**Key Features:**
- Connects to 3CX PostgreSQL database
- Fetches contacts in batches of 1000 for memory efficiency
- Supports multiple export formats
- Read-only operations (safe to run)

**Database Schema:**
- Table: `public.phonebook`
- Fields: idphonebook, firstname, lastname, phonenumber, company, tag, fkiddn, fkidtenant

### sync_exchange_contacts.py

Synchronizes 3CX phonebook contacts to Microsoft Exchange Server.

**Key Features:**
- Reads contacts from PostgreSQL database
- Connects to Exchange via EWS (Exchange Web Services)
- Normalizes phone numbers using `phonenumbers` library
- Validates email addresses with regex
- Creates or updates Exchange contacts
- Uses custom extended property `PhonebookId` to track contacts
- Supports contact folder management

**Database Schema:**
- Table: `public.phonebook`
- Additional fields: pv_an3 (mobile), pv_an1 (home), pv_an5 (email1), pv_an6 (email2)

**Phone Number Handling:**
- Business phone: `phonenumber` field
- Mobile phone: `pv_an3` field
- Home phone: `pv_an1` field
- Automatically formats to E.164 standard (e.g., +491234567890)

**Email Handling:**
- Email 1: `pv_an5` field
- Email 2: `pv_an6` field
- Basic validation for email format

## Dependencies

- **psycopg2-binary** - PostgreSQL adapter for sync_phonebook.py
- **psycopg** - Modern PostgreSQL adapter (psycopg3) for sync_exchange_contacts.py
- **exchangelib** - Microsoft Exchange Web Services client library
- **phonenumbers** - International phone number parsing and validation

## Troubleshooting

### Connection Issues

**PostgreSQL Connection Failed:**
- Verify PostgreSQL is running and accessible via Unix socket
- Check database name and user permissions
- Ensure the user has read access to the phonebook table

**Exchange Connection Failed:**
- Verify Exchange credentials are correct
- Check if EWS is enabled on your Exchange server
- Try enabling `EXCH_AUTODISCOVER=true` if using Office 365
- Verify network connectivity to Exchange server

### Data Issues

**Phone numbers not formatting correctly:**
- The script attempts to parse and format phone numbers to E.164 format
- If parsing fails, the original number is preserved
- Ensure phone numbers in the database include country codes

**Contacts not syncing:**
- Contacts without name, company, or phone number are skipped
- Check the dry-run output to see which contacts would be processed
- Use `--limit` flag to test with a small batch first

## Security Notes

- Store credentials securely (use environment variables, not hardcoded values)
- Consider using a dedicated Exchange service account with limited permissions
- The PostgreSQL connection uses read-only transactions for safety
- Review the `.gitignore` to ensure credentials files are not committed

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues, questions, or contributions, please [open an issue](https://github.com/yourusername/3cx_sync/issues).
