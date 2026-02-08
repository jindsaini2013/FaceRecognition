import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
# --- THIS WAS THE MISSING LINE ---
from google.oauth2.credentials import Credentials 
# -------------------------------

# We only need permission to read files
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    """
    Authenticates the user using credentials.json and returns a Drive service object.
    """
    creds = None
    
    # Check if we already have a valid token saved
    if os.path.exists('token.json'):
        # Now 'Credentials' is recognized
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # This opens the browser window for login
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    return service