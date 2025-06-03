import streamlit as st
from datetime import datetime, timedelta
import re
import os
from scheduler import get_calendar_service, find_meetings_with_person, remove_event
from autonomous_agent import SchedulingAgent

st.set_page_config(page_title="Autonomous Calendar Assistant", page_icon="📅")

def login_page():
    st.title("Login to Google Calendar")
    st.info("This app needs access to your Google Calendar to function properly.")
    
    if not os.path.exists('credentials.json'):
        st.error("Missing credentials.json file. Please add this file to your app directory.")
        st.write("""
        To get your credentials.json:
        1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
        2. Create a new project
        3. Enable the Google Calendar API
        4. Create OAuth credentials (Desktop application)
        5. Download the credentials file and save it as 'credentials.json' in the app directory
        """)
        return
    
    if st.button("Login with Google Calendar"):
        with st.spinner("Authenticating with Google..."):
            try:
                # Perform authentication - this will redirect if needed
                service = get_calendar_service()
                st.session_state['authenticated'] = True
                st.success("Authentication successful!")
                st.rerun()  # Rerun the app with authenticated state
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")

def agent_page():
    st.title("Autonomous Calendar Agent")
    
    try:
        # Get the service
        service = get_calendar_service()
        
        # Create our intelligent agent
        agent = SchedulingAgent(service)
        
        # User Interface
        st.write("### Your AI Calendar Assistant")
        st.write("I understand natural language. Tell me what you need help with for your calendar.")
        
        # Show user preferences
        with st.expander("Your Scheduling Preferences"):
            prefs = agent.preferences
            
            if prefs['preferred_days']:
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                st.write("**Preferred meeting days:**", [day_names[day] for day in prefs['preferred_days']])
            else:
                st.write("**Preferred meeting days:** Not enough data")
            
            if prefs['preferred_times']:
                st.write("**Preferred meeting times:**", [f"{hour}:00" for hour in prefs['preferred_times']])
            else:
                st.write("**Preferred meeting times:** Not enough data")
            
            st.write("**Typical meeting duration:**", f"{prefs['common_meeting_duration']} minutes")
            
            if prefs['frequent_contacts']:
                st.write("**People you meet with frequently:**")
                for contact in prefs['frequent_contacts'][:5]:
                    st.write(f"- {contact}")
        
        # Command input - larger text area for natural language
        command = st.text_area(
            "What would you like to do with your calendar?", 
            height=120,
            placeholder="Examples:\n- Schedule a meeting with Alex tomorrow at 2pm\n- Find all meetings with Morgan this month\n- Show my calendar for next Monday\n- When am I free tomorrow?\n- Check my availability for Friday"
        )
        
        # Process the command
        if st.button("Process", key="process_cmd"):
            if not command:
                st.warning("Please enter a command first.")
                return
                
            with st.spinner("Processing your request..."):
                # Convert command to lowercase for easier pattern matching
                command_lower = command.lower()
                
                # FINDING MEETINGS WITH PERSON
                if re.search(r'find.*(?:meeting|appointment).*with\s+(\w+)', command_lower) or \
                   re.search(r'show.*(?:meeting|appointment).*with\s+(\w+)', command_lower):
                    # Extract person name
                    person_match = re.search(r'(?:with|and)\s+(\w+(?:\s+\w+)?)', command_lower)
                    if person_match:
                        person = person_match.group(1).strip()
                        
                        # Extract time constraints if any
                        time_min = datetime.now().isoformat() + 'Z'
                        time_max = (datetime.now() + timedelta(days=30)).isoformat() + 'Z'
                        
                        if 'today' in command_lower:
                            today = datetime.now()
                            time_min = datetime.combine(today.date(), datetime.min.time()).isoformat() + 'Z'
                            time_max = datetime.combine(today.date(), datetime.max.time()).isoformat() + 'Z'
                        elif 'tomorrow' in command_lower:
                            tomorrow = datetime.now() + timedelta(days=1)
                            time_min = datetime.combine(tomorrow.date(), datetime.min.time()).isoformat() + 'Z'
                            time_max = datetime.combine(tomorrow.date(), datetime.max.time()).isoformat() + 'Z'
                        elif 'this week' in command_lower:
                            today = datetime.now()
                            start_of_week = today - timedelta(days=today.weekday())
                            end_of_week = start_of_week + timedelta(days=6)
                            time_min = datetime.combine(start_of_week.date(), datetime.min.time()).isoformat() + 'Z'
                            time_max = datetime.combine(end_of_week.date(), datetime.max.time()).isoformat() + 'Z'
                        elif 'this month' in command_lower:
                            today = datetime.now()
                            last_day = today.replace(day=28) + timedelta(days=4)  # Move to next month
                            last_day = last_day.replace(day=1) - timedelta(days=1)  # Last day of current month
                            time_min = datetime.combine(today.replace(day=1).date(), datetime.min.time()).isoformat() + 'Z'
                            time_max = datetime.combine(last_day.date(), datetime.max.time()).isoformat() + 'Z'
                        
                        # Find meetings with this person
                        meetings = find_meetings_with_person(service, "primary", person, time_min, time_max)
                        
                        if meetings:
                            st.success(f"I found {len(meetings)} meetings with {person}")
                            
                            for i, meeting in enumerate(meetings):
                                start_time = meeting['start']
                                if 'T' in start_time:
                                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                    formatted_time = start_dt.strftime("%A, %b %d, %Y at %I:%M %p")
                                else:
                                    formatted_time = start_time
                                    
                                with st.expander(f"{i+1}. {meeting['summary']} - {formatted_time}"):
                                    st.write(f"**Time:** {formatted_time}")
                                    st.markdown(f"[View in Calendar]({meeting['htmlLink']})")
                                    
                                    # Cancel button
                                    if st.button(f"Cancel this meeting", key=f"cancel_{i}"):
                                        result = remove_event(service, "primary", meeting['id'])
                                        st.success("Meeting cancelled!")
                                        st.rerun()
                        else:
                            st.info(f"I couldn't find any meetings with {person} in the specified time range.")
                
                # VIEWING CALENDAR FOR A SPECIFIC DAY
                elif re.search(r'(?:show|view|display).*(?:calendar|schedule|meeting).*(?:for|on)\s+(\w+)', command_lower) or \
                     re.search(r'what.*(?:calendar|schedule|meeting).*(?:for|on)\s+(\w+)', command_lower):
                    # Try to extract date
                    date_value = None
                    
                    if 'today' in command_lower:
                        date_value = datetime.now().date()
                    elif 'tomorrow' in command_lower:
                        date_value = (datetime.now() + timedelta(days=1)).date()
                    else:
                        # Extract day name if present
                        day_mapping = {
                            'monday': 0, 'tuesday': 1, 'wednesday': 2, 
                            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
                        }
                        
                        for day_name, day_number in day_mapping.items():
                            if day_name in command_lower:
                                today = datetime.now()
                                days_ahead = (day_number - today.weekday()) % 7
                                if days_ahead == 0:  # Today
                                    if 'next' in command_lower:
                                        days_ahead = 7  # Next week
                                date_value = (today + timedelta(days=days_ahead)).date()
                                break
                    
                    if date_value:
                        # Get the day's events
                        start_dt = datetime.combine(date_value, datetime.min.time())
                        end_dt = datetime.combine(date_value, datetime.max.time())
                        
                        time_min = start_dt.isoformat() + 'Z'
                        time_max = end_dt.isoformat() + 'Z'
                        
                        try:
                            events_result = service.events().list(
                                calendarId="primary",
                                timeMin=time_min,
                                timeMax=time_max,
                                singleEvents=True,
                                orderBy='startTime'
                            ).execute()
                            
                            events = events_result.get('items', [])
                            
                            if events:
                                st.success(f"Here's your schedule for {date_value.strftime('%A, %B %d')}:")
                                
                                for i, event in enumerate(events):
                                    summary = event.get('summary', 'No Title')
                                    start = event['start'].get('dateTime', event['start'].get('date'))
                                    
                                    if 'T' in start:
                                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                                        time_str = start_dt.strftime("%I:%M %p")
                                    else:
                                        time_str = "All day"
                                    
                                    with st.expander(f"{summary} - {time_str}"):
                                        st.write(f"**Event:** {summary}")
                                        st.write(f"**Time:** {time_str}")
                                        st.markdown(f"[View in Calendar]({event.get('htmlLink', '#')})")
                                        
                                        # Cancel button
                                        if st.button("Cancel this event", key=f"cancel_event_{i}"):
                                            result = remove_event(service, "primary", event['id'])
                                            st.success("Event cancelled!")
                                            st.rerun()
                            else:
                                st.info(f"You have no events scheduled for {date_value.strftime('%A, %B %d')}.")
                        except Exception as e:
                            st.error(f"Error fetching events: {str(e)}")
                    else:
                        # Let the agent handle complex date parsing
                        result = agent.process_command(command)
                        if result["status"] != "error":
                            st.info(result["message"])
                        else:
                            st.error(f"I couldn't understand the date in your request. Please try again with a clearer date specification.")
                
                # CHECKING AVAILABILITY
                elif re.search(r'(?:when|what time).*(?:free|available)', command_lower) or \
                     re.search(r'check.*availability', command_lower) or \
                     re.search(r'am i free', command_lower):
                    # Try to extract date
                    date_value = None
                    
                    if 'today' in command_lower:
                        date_value = datetime.now().date()
                    elif 'tomorrow' in command_lower:
                        date_value = (datetime.now() + timedelta(days=1)).date()
                    else:
                        # Extract day name if present
                        day_mapping = {
                            'monday': 0, 'tuesday': 1, 'wednesday': 2, 
                            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
                        }
                        
                        for day_name, day_number in day_mapping.items():
                            if day_name in command_lower:
                                today = datetime.now()
                                days_ahead = (day_number - today.weekday()) % 7
                                if days_ahead == 0:  # Today
                                    if 'next' in command_lower:
                                        days_ahead = 7  # Next week
                                date_value = (today + timedelta(days=days_ahead)).date()
                                break
                    
                    # Default to tomorrow if no date found
                    if not date_value:
                        date_value = datetime.now().date() + timedelta(days=1)
                    
                    # Set default business hours
                    start_hour = 9
                    end_hour = 17
                    
                    # Check availability
                    start_dt = datetime.combine(date_value, datetime.min.time().replace(hour=start_hour))
                    end_dt = datetime.combine(date_value, datetime.min.time().replace(hour=end_hour))
                    
                    time_min = start_dt.isoformat() + 'Z'
                    time_max = end_dt.isoformat() + 'Z'
                    
                    try:
                        # Query the freebusy API
                        freebusy_query = {
                            "timeMin": time_min,
                            "timeMax": time_max,
                            "items": [{"id": "primary"}]
                        }
                        
                        freebusy_result = service.freebusy().query(body=freebusy_query).execute()
                        busy_slots = freebusy_result['calendars']['primary']['busy']
                        
                        st.success(f"Here's your availability for {date_value.strftime('%A, %B %d')}:")
                        
                        if busy_slots:
                            # Create a list of hours and availability
                            hour_slots = []
                            for hour in range(start_hour, end_hour + 1):
                                slot_start = datetime.combine(date_value, datetime.min.time().replace(hour=hour))
                                slot_end = slot_start + timedelta(hours=1)
                                
                                # Check if this slot overlaps with any busy time
                                is_busy = False
                                for busy in busy_slots:
                                    busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                                    busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                                    
                                    if (slot_start < busy_end and slot_end > busy_start):
                                        is_busy = True
                                        break
                                
                                hour_slots.append({
                                    "hour": hour,
                                    "time_str": slot_start.strftime("%I:%M %p"),
                                    "is_busy": is_busy
                                })
                            
                            # Display as a table
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.markdown("**Time**")
                                for slot in hour_slots:
                                    st.write(slot["time_str"])
                            with col2:
                                st.markdown("**Status**")
                                for slot in hour_slots:
                                    if slot["is_busy"]:
                                        st.markdown("🔴 Busy")
                                    else:
                                        st.markdown("🟢 Available")
                        else:
                            st.info(f"You're completely free on {date_value.strftime('%A, %B %d')} from {start_hour}:00 to {end_hour}:00!")
                    except Exception as e:
                        st.error(f"Error checking availability: {str(e)}")
                
                # DEFAULT: Let the agent handle all other commands
                else:
                    result = agent.process_command(command)
                    
                    if result["status"] == "created":
                        st.success(result["message"])
                        st.markdown(f"[View in Calendar]({result['event_link']})")
                        
                        # Show alternatives if available
                        if "alternatives" in result and result["alternatives"]:
                            st.markdown("**Alternative times that would also work:**")
                            for i, alt in enumerate(result["alternatives"]):
                                if isinstance(alt, dict) and 'start' in alt:
                                    start_dt = datetime.fromisoformat(alt['start'].replace('Z', '+00:00'))
                                    st.write(f"{i+1}. {start_dt.strftime('%A, %b %d at %I:%M %p')}")
                    
                    elif result["status"] == "rescheduled":
                        st.warning(result["message"])
                        st.markdown(f"[View in Calendar]({result['event_link']})")
                    
                    elif result["status"] == "suggestions":
                        st.info(result["message"])
                        for i, slot in enumerate(result["slots"]):
                            st.write(f"{i+1}. {slot}")
                    
                    else:
                        st.error(result["message"])
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Try restarting the application if the issue persists.")

# Main app logic
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# Add logout button in sidebar
if st.session_state['authenticated']:
    if st.sidebar.button("Logout"):
        st.session_state['authenticated'] = False
        if 'user_token' in st.session_state:
            del st.session_state['user_token']
        st.rerun()

# Show appropriate page
if st.session_state['authenticated']:
    agent_page()
else:
    login_page()
