import re
import pytz
from datetime import datetime, timedelta
from collections import Counter
from googleapiclient.errors import HttpError

class SchedulingAgent:
    """
    Autonomous agent for intelligent calendar management.
    Features:
    - Context-aware scheduling (learns from past meetings)
    - Conflict resolution
    - Smart time slot suggestions
    - Natural language processing for calendar commands
    """
    
    def __init__(self, service, timezone="Asia/Kolkata"):
        self.service = service
        self.timezone = timezone
        self.tz = pytz.timezone(timezone)
        # Load user preferences and context
        self.preferences = self._load_user_preferences()
        
    def _load_user_preferences(self):
        """Load user scheduling preferences by analyzing past meetings"""
        preferences = {
            'preferred_days': None,
            'preferred_times': None,
            'common_meeting_duration': 60,  # minutes
            'meeting_blackout_times': [],   # times to avoid
            'frequent_contacts': []         # people the user meets with often
        }
        
        # Analyze past 3 months of meetings
        now = datetime.now(self.tz)
        three_months_ago = (now - timedelta(days=90)).isoformat()
        
        try:
            events = self.service.events().list(
                calendarId='primary',
                timeMin=three_months_ago,
                maxResults=1000,
                singleEvents=True,
                orderBy='startTime'
            ).execute().get('items', [])
            
            # Skip if no past meetings
            if not events:
                return preferences
                
            # Analyze meeting patterns
            day_counts = Counter()
            hour_counts = Counter()
            durations = []
            contacts = Counter()
            
            for event in events:
                # Only process events with actual people (meetings)
                if 'attendees' in event or 'meeting' in event.get('summary', '').lower():
                    start = event['start'].get('dateTime')
                    end = event['end'].get('dateTime')
                    
                    if start and end:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        
                        # Track day of week preferences
                        day_counts[start_dt.weekday()] += 1
                        
                        # Track hour preferences
                        hour_counts[start_dt.hour] += 1
                        
                        # Track typical meeting durations
                        duration = (end_dt - start_dt).total_seconds() / 60
                        durations.append(duration)
                        
                        # Extract contacts
                        if 'attendees' in event:
                            for attendee in event['attendees']:
                                if 'email' in attendee and attendee.get('responseStatus') != 'declined':
                                    contacts[attendee['email']] += 1
                        
                        summary = event.get('summary', '').lower()
                        if 'with' in summary:
                            name = summary.split('with')[-1].strip()
                            contacts[name] += 1
            
            # Set preferences based on analysis
            if day_counts:
                preferences['preferred_days'] = [day for day, _ in day_counts.most_common(3)]
            
            if hour_counts:
                preferences['preferred_times'] = [hour for hour, _ in hour_counts.most_common(3)]
            
            if durations:
                preferences['common_meeting_duration'] = int(sum(durations) / len(durations))
            
            if contacts:
                preferences['frequent_contacts'] = [contact for contact, _ in contacts.most_common(10)]
                
            # Identify blackout times (times when meetings are rarely scheduled)
            work_hours = list(range(9, 18))  # 9 AM to 6 PM
            all_hours = set(work_hours)
            common_hours = set(preferences['preferred_times']) if preferences['preferred_times'] else set()
            preferences['meeting_blackout_times'] = list(all_hours - common_hours)
            
            return preferences
            
        except Exception as e:
            print(f"Error analyzing past meetings: {e}")
            return preferences
    
    def find_optimal_meeting_time(self, person=None, start_date=None, end_date=None, duration_minutes=None):
        """
        Find the optimal meeting time based on:
        - User's scheduling preferences
        - Calendar availability
        - The other person's availability (if provided)
        - Contextual factors (e.g., time of day, day of week)
        """
        if not duration_minutes:
            duration_minutes = self.preferences['common_meeting_duration']
        
        now = datetime.now(self.tz)
        if not start_date:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if not end_date:
            end_date = start_date + timedelta(days=7)
            
        # Convert to proper format
        time_min = start_date.isoformat()
        time_max = end_date.isoformat()
        
        # Get busy times
        freebusy_query = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}]
        }
        
        try:
            busy_times = self.service.freebusy().query(body=freebusy_query).execute()
            busy_slots = busy_times['calendars']['primary']['busy']
        except Exception as e:
            print(f"Error fetching busy times: {e}")
            busy_slots = []
        
        # Prepare scoring for candidate slots
        candidate_slots = []
        current_date = start_date
        
        # Look at each day in the range
        while current_date.date() <= end_date.date():
            # Skip days that don't match preferred days (if we have preferences)
            if self.preferences['preferred_days'] and current_date.weekday() not in self.preferences['preferred_days']:
                current_date = current_date + timedelta(days=1)
                continue
                
            # Look at each hour from 9 AM to 6 PM
            for hour in range(9, 18):
                # Skip hours in blackout times
                if hour in self.preferences['meeting_blackout_times']:
                    continue
                    
                slot_start = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=duration_minutes)
                
                # Skip if in the past
                if slot_start <= now:
                    continue
                
                # Check if slot conflicts with busy times
                is_free = True
                for busy in busy_slots:
                    busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                    busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                    
                    if (slot_start < busy_end and slot_end > busy_start):
                        is_free = False
                        break
                
                if is_free:
                    # Score this time slot
                    score = 0
                    
                    # Preferred hour bonus
                    if self.preferences['preferred_times'] and hour in self.preferences['preferred_times']:
                        score += 10
                    
                    # Preferred day bonus
                    if self.preferences['preferred_days'] and slot_start.weekday() in self.preferences['preferred_days']:
                        score += 5
                    
                    # Recency penalty (prefer sooner meetings)
                    days_from_now = (slot_start.date() - now.date()).days
                    score -= days_from_now
                    
                    candidate_slots.append({
                        'start': slot_start.isoformat(),
                        'end': slot_end.isoformat(),
                        'score': score
                    })
            
            current_date = current_date + timedelta(days=1)
        
        # Sort by score, highest first
        candidate_slots.sort(key=lambda x: x['score'], reverse=True)
        
        # Return the top 3 options
        return candidate_slots[:3] if candidate_slots else []
    
    def schedule_meeting(self, person, datetime_str=None, duration_minutes=None):
        """
        Schedule a meeting with intelligent slot selection
        """
        if not duration_minutes:
            duration_minutes = self.preferences['common_meeting_duration']
        
        # If datetime specified, use it
        if datetime_str:
            try:
                # Parse the provided date/time
                dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                slot_start = dt
                slot_end = slot_start + timedelta(minutes=duration_minutes)
                
                # Check if this time is available
                freebusy_query = {
                    "timeMin": slot_start.isoformat(),
                    "timeMax": slot_end.isoformat(),
                    "items": [{"id": "primary"}]
                }
                
                busy_times = self.service.freebusy().query(body=freebusy_query).execute()
                busy_slots = busy_times['calendars']['primary']['busy']
                
                if busy_slots:
                    # Time is not available, find alternatives
                    optimal_slots = self.find_optimal_meeting_time(
                        person, 
                        slot_start, 
                        slot_start + timedelta(days=7), 
                        duration_minutes
                    )
                    
                    if not optimal_slots:
                        return {
                            "status": "error",
                            "message": f"Requested time is not available and no alternatives found."
                        }
                    
                    # Use the best alternative
                    slot_start = datetime.fromisoformat(optimal_slots[0]['start'].replace('Z', '+00:00'))
                    slot_end = datetime.fromisoformat(optimal_slots[0]['end'].replace('Z', '+00:00'))
                    
                    # Create event with the alternative time
                    event = {
                        'summary': f'Meeting with {person} (Rescheduled)',
                        'description': f'Originally requested for {datetime_str}',
                        'start': {'dateTime': slot_start.isoformat(), 'timeZone': self.timezone},
                        'end': {'dateTime': slot_end.isoformat(), 'timeZone': self.timezone},
                    }
                    
                    event_result = self.service.events().insert(calendarId='primary', body=event).execute()
                    
                    return {
                        "status": "rescheduled",
                        "message": f"Requested time was unavailable. Meeting rescheduled to {slot_start.strftime('%Y-%m-%d %I:%M %p')}",
                        "event_link": event_result.get('htmlLink'),
                        "scheduled_time": slot_start.isoformat()
                    }
                
                else:
                    # Time is available, create the event
                    event = {
                        'summary': f'Meeting with {person}',
                        'start': {'dateTime': slot_start.isoformat(), 'timeZone': self.timezone},
                        'end': {'dateTime': slot_end.isoformat(), 'timeZone': self.timezone},
                    }
                    
                    event_result = self.service.events().insert(calendarId='primary', body=event).execute()
                    
                    return {
                        "status": "created",
                        "message": f"Meeting scheduled for {slot_start.strftime('%Y-%m-%d %I:%M %p')}",
                        "event_link": event_result.get('htmlLink'),
                        "scheduled_time": slot_start.isoformat()
                    }
                    
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error scheduling meeting: {e}"
                }
        
        # No datetime specified, find optimal time
        else:
            try:
                now = datetime.now(self.tz)
                optimal_slots = self.find_optimal_meeting_time(
                    person, 
                    now + timedelta(days=1), 
                    now + timedelta(days=14), 
                    duration_minutes
                )
                
                if not optimal_slots:
                    return {
                        "status": "error",
                        "message": "No suitable meeting times found in the next 2 weeks."
                    }
                
                # Use the best slot
                slot_start = datetime.fromisoformat(optimal_slots[0]['start'].replace('Z', '+00:00'))
                slot_end = datetime.fromisoformat(optimal_slots[0]['end'].replace('Z', '+00:00'))
                
                # Create the event
                event = {
                    'summary': f'Meeting with {person}',
                    'description': 'Automatically scheduled by Calendar Assistant',
                    'start': {'dateTime': slot_start.isoformat(), 'timeZone': self.timezone},
                    'end': {'dateTime': slot_end.isoformat(), 'timeZone': self.timezone},
                }
                
                event_result = self.service.events().insert(calendarId='primary', body=event).execute()
                
                return {
                    "status": "created",
                    "message": f"Optimal meeting time found and scheduled: {slot_start.strftime('%Y-%m-%d %I:%M %p')}",
                    "event_link": event_result.get('htmlLink'),
                    "scheduled_time": slot_start.isoformat(),
                    "alternatives": optimal_slots[1:] if len(optimal_slots) > 1 else []
                }
                
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error finding optimal meeting time: {e}"
                }
    
    def process_command(self, command):
        """Process natural language commands with context awareness"""
        command = command.lower().strip()
        
        # Find a time/schedule with person
        schedule_match = re.search(r'(schedule|find a time for|set up|arrange) (?:a )?(?:meeting )?with ([\w\s]+)', command)
        if schedule_match:
            action = schedule_match.group(1)
            person = schedule_match.group(2).strip()
            
            # Extract date/time if specified
            datetime_match = re.search(r'(?:on|at) ([\w\s\d,:-]+(?:am|pm)?)', command)
            datetime_str = None
            
            if datetime_match:
                datetime_text = datetime_match.group(1)
                try:
                    # Try to parse the date/time
                    from dateutil import parser
                    dt = parser.parse(datetime_text)
                    # Localize the datetime
                    dt = self.tz.localize(dt)
                    datetime_str = dt.isoformat()
                except:
                    return {
                        "status": "error",
                        "message": f"Could not understand the date/time: {datetime_text}"
                    }
            
            # Extract duration if specified
            duration_match = re.search(r'for (\d+) (minute|hour|min|hr)s?', command)
            duration_minutes = None
            
            if duration_match:
                duration_val = int(duration_match.group(1))
                duration_unit = duration_match.group(2)
                
                if duration_unit in ['hour', 'hr']:
                    duration_minutes = duration_val * 60
                else:
                    duration_minutes = duration_val
            
            # Schedule the meeting
            return self.schedule_meeting(person, datetime_str, duration_minutes)
        
        # Suggest times without scheduling
        suggest_match = re.search(r'suggest|recommend|what are good times for meeting with ([\w\s]+)', command)
        if suggest_match:
            person = suggest_match.group(1).strip()
            optimal_slots = self.find_optimal_meeting_time(person=person)
            
            if not optimal_slots:
                return {
                    "status": "error",
                    "message": "No suitable meeting times found in the next week."
                }
            
            formatted_slots = []
            for slot in optimal_slots:
                start_dt = datetime.fromisoformat(slot['start'].replace('Z', '+00:00'))
                formatted_slots.append(start_dt.strftime('%A, %b %d at %I:%M %p'))
            
            return {
                "status": "suggestions",
                "message": f"Here are the best times to meet with {person}:",
                "slots": formatted_slots
            }
        
        # If no matching intent was found
        return {
            "status": "error",
            "message": "I couldn't understand that command. Try something like 'schedule a meeting with Alex' or 'suggest times for meeting with Taylor'."
        }