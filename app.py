# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import pymongo
import requests
from bs4 import BeautifulSoup
import google.auth.transport.requests
from google.oauth2 import id_token
from googleapiclient.discovery import build
import datetime
import os

app = Flask(__name__)
CORS(app)

# Secrets - Set these as environment variables in production
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-openai-key')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', 'your-google-client-id')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/hacktrack')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'your-google-api-key')  # For Calendar

openai.api_key = OPENAI_API_KEY
client = pymongo.MongoClient(MONGO_URI)
db = client['hacktrack']
users = db['users']
events_col = db['events']  # Stored events from scraping

# Example event sources (add more as needed)
EVENT_SOURCES = [
    'https://devpost.com/hackathons',
    'https://www.hackerearth.com/challenges/',
    # Add more sites
]

# Periodic scraping (in production, use scheduler like APScheduler)
def scrape_events():
    all_events = []
    for url in EVENT_SOURCES:
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Parsing logic - this is placeholder; customize per site
            for item in soup.find_all('div', class_='event'):  # Adjust selectors
                event = {
                    'id': str(hash(item.text)),  # Unique ID
                    'name': item.find('h3').text if item.find('h3') else 'Unknown',
                    'date': item.find('span', class_='date').text if item.find('span', class_='date') else 'TBD',
                    'location': item.find('span', class_='location').text if item.find('span', class_='location') else 'Online',
                    'skills': 'AI, Coding'  # Extract properly
                }
                all_events.append(event)
        except Exception as e:
            print(f'Error scraping {url}: {e}')
    # Store in DB
    events_col.delete_many({})
    if all_events:
        events_col.insert_many(all_events)

# Call scrape on startup (in prod, schedule)
scrape_events()

def verify_google_token(token):
    try:
        idinfo = id_token.verify_oauth2_token(token, google.auth.transport.requests.Request(), GOOGLE_CLIENT_ID)
        return idinfo['sub'], idinfo['email']
    except ValueError:
        return None, None

@app.route('/api/chat', methods=['POST'])
def chat():
    token = request.headers.get('Authorization', '').split('Bearer ')[-1]
    user_id, email = verify_google_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    message = request.json['message']

    # Fetch events from DB
    events = list(events_col.find())

    # Personalization: Extract filters from message (simple parsing)
    # For real, use NLP or regex
    location = 'Rajasthan' if 'Rajasthan' in message else None
    skills = 'AI' if 'AI' in message else None
    filtered_events = [e for e in events if (not location or location in e['location']) and (not skills or skills in e['skills'])]

    # Use OpenAI for chat response
    prompt = f"User query: {message}\nAvailable events: {filtered_events}\nProvide personalized recommendations."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are HackTrack AI, helping with competitions."},
                  {"role": "user", "content": prompt}]
    )
    reply = response['choices'][0]['message']['content']

    return jsonify({'reply': reply, 'events': filtered_events[:5]})  # Limit to 5

@app.route('/api/save-event', methods=['POST'])
def save_event():
    token = request.headers.get('Authorization', '').split('Bearer ')[-1]
    user_id, _ = verify_google_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    event_id = request.json['eventId']
    event = events_col.find_one({'id': event_id})
    if event:
        users.update_one({'user_id': user_id}, {'$addToSet': {'saved_events': event}}, upsert=True)
        return jsonify({'success': True})
    return jsonify({'error': 'Event not found'}), 404

@app.route('/api/saved-events', methods=['GET'])
def get_saved_events():
    token = request.headers.get('Authorization', '').split('Bearer ')[-1]
    user_id, _ = verify_google_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    user = users.find_one({'user_id': user_id})
    return jsonify(user.get('saved_events', []))

@app.route('/api/set-reminder', methods=['POST'])
def set_reminder():
    token = request.headers.get('Authorization', '').split('Bearer ')[-1]
    user_id, email = verify_google_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    event_id = request.json['eventId']
    event = events_col.find_one({'id': event_id})
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    # Google Calendar API
    # Note: In prod, handle credentials properly; here assume token has calendar scope
    # For simplicity, use service account or adjust
    # This is placeholder; implement OAuth flow for user's calendar
    service = build('calendar', 'v3', developerKey=GOOGLE_API_KEY)  # Use proper auth

    calendar_event = {
        'summary': event['name'],
        'description': 'Reminder for hackathon',
        'start': {'dateTime': datetime.datetime.now().isoformat()},  # Adjust to event date -1 day
        'end': {'dateTime': (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()},
        'attendees': [{'email': email}],
        'reminders': {'useDefault': True}
    }
    service.events().insert(calendarId='primary', body=calendar_event).execute()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)