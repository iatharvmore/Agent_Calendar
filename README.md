# Autonomous Agent for Calendar Management Documentation

## Overview

Build an agent that interacts with your calendar and inbox to schedule meetings, resolve conflicts, and optimize your day autonomously. It should understand intent (e.g., “find a time next week with Alex”) and act accordingly.

## Project Structure

```
DAssault/
├── app.py                 # Main Streamlit application
├── scheduler.py           # Google Calendar API interaction functions
├── autonomous_agent.py    # AI scheduling agent with learning capabilities
├── requirements.txt       # Python dependencies
├── token.json             # User authentication token (generated upon login)
├── credentials.json       # Google API credentials file
└── documentation.md       # This documentation file
```

## Components

### 1. app.py

The main application file built with Streamlit that provides the user interface and handles the logic for processing natural language commands.

#### Key Features:
- Authentication with Google Calendar
- Natural language command processing
- Interactive calendar views
- Meeting management functionality (schedule, find, cancel, reschedule)
- Availability checking

#### Main Functions:
- `login_page()`: Handles Google Calendar authentication
- `agent_page()`: Displays the main interface after authentication
- Command processing logic for different types of requests

### 2. scheduler.py

Handles direct interactions with the Google Calendar API and provides utility functions for calendar operations.

#### Key Functions:
- `get_calendar_service()`: Authenticates with Google and returns a service object
- `parse_command()`: Extracts meeting details from natural language
- `check_availability()`: Checks if a time slot is available
- `find_next_available_slot()`: Finds the next free slot on a given day
- `create_event()`: Creates a new calendar event
- `find_meetings_with_person()`: Searches for meetings with a specific person
- `remove_event()`: Cancels/deletes a calendar event
- `reschedule_event()`: Changes the time of an existing event

### 3. autonomous_agent.py

Contains the AI agent that learns from your calendar patterns and provides intelligent scheduling assistance.

#### Key Features:
- Analyzes past meeting patterns to learn preferences
- Makes intelligent scheduling decisions
- Suggests optimal meeting times
- Understands complex natural language requests

## Authentication Flow

1. User clicks "Login with Google Calendar"
2. Application requests OAuth permissions for calendar access
3. User approves access in Google's authentication page
4. Google returns an authentication token
5. Token is stored in `token.json` for future sessions

## Natural Language Commands

The application understands various types of natural language commands:

### Scheduling Commands
- "Schedule a meeting with Alex tomorrow at 2pm"
- "Set up a 30 minute call with Morgan next Friday"
- "Book a 1 hour meeting with the team on Monday"

### Finding Commands
- "Find all meetings with Alex"
- "Show me meetings for next Monday"
- "What meetings do I have with the team this month?"

### Managing Commands
- "Cancel my meeting with Alex on Friday"
- "Reschedule my call with Morgan to next Tuesday at 3pm"
- "Move my 2pm meeting to 4pm tomorrow"

### Availability Commands
- "When am I free tomorrow?"
- "Check my availability for next Wednesday"
- "Find a free slot for a 2 hour meeting next week"

## Time Zone Handling

The application uses the Asia/Kolkata time zone (UTC+5:30) by default for all calendar operations. This is configured in the event creation and retrieval functions.

## Error Handling

The application includes error handling for various scenarios:
- Authentication failures
- Calendar API errors
- Meeting scheduling conflicts
- Invalid date/time formats

## Usage Examples

### Example 1: Scheduling a Meeting
1. Enter: "Schedule a meeting with Alex tomorrow at 2pm"
2. The assistant will:
   - Check if the time slot is available
   - Create the event if free
   - Suggest alternative times if the slot is busy

### Example 2: Finding Meetings
1. Enter: "Find all meetings with Morgan this month"
2. The assistant will display all meetings with Morgan in the current month

### Example 3: Checking Availability
1. Enter: "When am I free on Friday?"
2. The assistant will show your free/busy slots for the specified day

## Installation and Setup

### Prerequisites
- Python 3.7 or higher
- Google Calendar API credentials

### Installation Steps
1. Clone the repository or download the files
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Place your Google Calendar API credentials in the project directory as `credentials.json`
4. Run the application:
   ```
   streamlit run app.py
   ```
5. Navigate to http://localhost:8501 in your browser

## Google Calendar API Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Calendar API
4. Create OAuth credentials (Desktop application)
5. Download the credentials and save as `credentials.json` in the project directory

## Future Enhancements

Potential future improvements for the Calendar Assistant:
- Multiple calendar support
- Meeting templates for recurring meetings
- Integration with meeting platforms (Zoom, Teams, etc.)
- Mobile application version
- Email notifications for scheduled meetings
- Collaborative scheduling with other users
- Advanced conflict resolution strategies

## Troubleshooting

### Common Issues:

#### Authentication Problems
- Ensure `credentials.json` is properly formatted and contains valid credentials
- Try deleting `token.json` and re-authenticating
- Check that the Google Calendar API is enabled in your Google Cloud project


