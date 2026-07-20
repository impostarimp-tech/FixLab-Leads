"""One-off helper: exports the local token.pickle (already authorized via the
interactive Google login) as JSON, for use as the GOOGLE_OAUTH_TOKEN_JSON
environment variable on a hosted deployment. Run this locally where
token.pickle already exists and works; never commit the output anywhere."""
import pickle

from google.auth.transport.requests import Request

TOKEN_FILE = "token.pickle"

with open(TOKEN_FILE, "rb") as f:
    creds = pickle.load(f)

if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

print(creds.to_json())
