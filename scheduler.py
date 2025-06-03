from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import re
import os

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
def get_calendar_service():
    """
    Returns a Google Calendar service object for the current user.
    Uses a simple local token approach for authentication.
    """
    import json
    
    creds = None
    token_path = 'token.json'
    
    # Check if token file exists
    if os.path.exists(token_path):
        with open(token_path, 'r') as token_file:
            creds = Credentials.from_authorized_user_info(json.load(token_file), SCOPES)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save credentials to token file
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())
    
    return build('calendar', 'v3', credentials=creds)

def parse_command(command):
    summary = "Meeting"
    calendar_id = "primary"
    date = (datetime(2025, 6, 9)).strftime('%Y-%m-%d')  # Next Monday
    time = "14:00:00"
    if "with" in command.lower():
        summary = "Meeting with " + command.split('with')[-1].strip().split(' at ')[0].split(' on ')[0]
    time_match = re.search(r'(\d{1,2})\s*(AM|PM)', command, re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        period = time_match.group(2).upper()
        if period == "PM" and hour != 12:
            hour += 12
        elif period == "AM" and hour == 12:
            hour = 0
        time = f"{hour:02d}:00:00"
    if "on" in command.lower():
        calendar_part = command.split('on')[-1].strip().lower()
        if calendar_part != "my calendar":
            calendar_id = calendar_part.replace("’s calendar", "").strip()
    start_time = f"{date}T{time}+05:30"
    return summary, start_time, calendar_id

def check_availability(service, calendar_id, start_time, end_time):
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return len(events_result.get('items', [])) == 0
    except HttpError as e:
        print(f"Error accessing calendar {calendar_id}: {e}")
        return False

def find_next_available_slot(service, calendar_id, start_time, duration_hours=1, max_attempts=8):
    """
    Finds the next available slot of given duration (in hours) on the same day as start_time.
    Tries up to max_attempts slots, each duration_hours apart, but only within the same day.
    """
    start_dt = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S%z')
    day_end = start_dt.replace(hour=23, minute=59, second=59)
    for i in range(max_attempts):
        candidate_start = start_dt + timedelta(hours=i)
        candidate_end = candidate_start + timedelta(hours=duration_hours)
        # Only consider slots within the same day
        if candidate_start.date() != start_dt.date() or candidate_end > day_end:
            break
        candidate_start_str = candidate_start.isoformat()
        candidate_end_str = candidate_end.isoformat()
        if check_availability(service, calendar_id, candidate_start_str, candidate_end_str):
            # Add return of slot info for UI display
            return candidate_start_str, candidate_end_str
    return None, None

def create_event(service, summary, start_time, calendar_id):
    duration_hours = 1
    end_time = (datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S%z') + timedelta(hours=duration_hours)).isoformat()
    if check_availability(service, calendar_id, start_time, end_time):
        event = {
            'summary': summary,
            'start': {'dateTime': start_time, 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end_time, 'timeZone': 'Asia/Kolkata'},
        }
        try:
            event_result = service.events().insert(calendarId=calendar_id, body=event).execute()
            return {
                "status": "created",
                "message": f"Event created: {event_result.get('htmlLink')}",
                "event_link": event_result.get('htmlLink'),
                "scheduled_time": start_time
            }
        except HttpError as e:
            return {
                "status": "error",
                "message": f"Error creating event: {e}"
            }
    else:
        # Try to find next available slot on the same day
        next_start, next_end = find_next_available_slot(service, calendar_id, start_time, duration_hours)
        requested_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S%z').strftime('%Y-%m-%d at %I:%M %p')
        if next_start and next_end:
            event = {
                'summary': summary + " (Rescheduled)",
                'start': {'dateTime': next_start, 'timeZone': 'Asia/Kolkata'},
                'end': {'dateTime': next_end, 'timeZone': 'Asia/Kolkata'},
            }
            try:
                event_result = service.events().insert(calendarId=calendar_id, body=event).execute()
                resched_time = datetime.strptime(next_start, '%Y-%m-%dT%H:%M:%S%z').strftime('%Y-%m-%d at %I:%M %p')
                return {
                    "status": "rescheduled",
                    "message": (f"Requested time slot unavailable on {requested_time}. "
                                f"Event rescheduled: {event_result.get('htmlLink')} at {resched_time}"),
                    "event_link": event_result.get('htmlLink'),
                    "scheduled_time": resched_time,
                    "original_time": requested_time
                }
            except HttpError as e:
                return {
                    "status": "error",
                    "message": f"Error creating event: {e}"
                }
        else:
            return {
                "status": "no_slot",
                "message": f"No available slots found on {requested_time} for the day.",
                "original_time": requested_time
            }

def find_meetings_with_person(service, calendar_id, person_name, time_min=None, time_max=None):
    """
    Finds meetings with a specific person in the summary.
    """
    if not time_min:
        time_min = datetime.now().isoformat() + 'Z'
    if not time_max:
        time_max = (datetime.now() + timedelta(days=30)).isoformat() + 'Z'
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            q=person_name
        ).execute()
        meetings = [
            {
                'id': event['id'],
                'summary': event.get('summary', ''),
                'start': event['start'].get('dateTime', event['start'].get('date')),
                'end': event['end'].get('dateTime', event['end'].get('date')),
                'htmlLink': event.get('htmlLink', '')
            }
            for event in events_result.get('items', [])
            if person_name.lower() in event.get('summary', '').lower()
        ]
        return meetings
    except HttpError as e:
        print(f"Error finding meetings: {e}")
        return []

def remove_event(service, calendar_id, event_id):
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return "Event removed successfully."
    except HttpError as e:
        return f"Error removing event: {e}"

def reschedule_event(service, calendar_id, event_id, new_start_time, duration_hours=1):
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        new_end_time = (datetime.strptime(new_start_time, '%Y-%m-%dT%H:%M:%S%z') + timedelta(hours=duration_hours)).isoformat()
        event['start']['dateTime'] = new_start_time
        event['end']['dateTime'] = new_end_time
        updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        return f"Event rescheduled: {updated_event.get('htmlLink')}"
    except HttpError as e:
        return f"Error rescheduling event: {e}"

def parse_find_command(command):
    """
    Parses commands like 'find me meeting with Alex'
    """
    match = re.search(r'find.*meeting with ([\w\s]+)', command, re.IGNORECASE)
    if match:
        person = match.group(1).strip()
        return person
    return None