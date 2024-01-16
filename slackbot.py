#Our Importations
import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import string
from datetime import datetime, timedelta

#Initializing and Loading our environment paths
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

#Represents Flask configuration
#NGROK connects this code to a web server for realtime feedback
app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(os.environ['SIGNING_SECRET'], '/slack/events', app)

#Web Client for Slack and loading our token
#We like to initialize it into an environment so it protects data instead of a text file
client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
BOT_ID = client.api_call("auth.test")['user_id']

message_counts = {}
welcome_messages = {}

BAD_WORDS = ['bad word 1', 'bad word 2', 'bad word 3']

SCHEDULED_MESSAGES = [
    {'text': 'First message', 'post_at': (
        datetime.now() + timedelta(seconds=20)).timestamp(), 'channel': 'C05NNFUC05S'},
    {'text': 'Second Message!', 'post_at': (
        datetime.now() + timedelta(seconds=30)).timestamp(), 'channel': 'C05NNFUC05S'}
]

#Welcome Message Class --------------------------------------------------
class WelcomeMessage:
    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Welcome to this awesome channel! \n\n'
                '*Get started by completing the tasks!*'
            )
        }
    }

    DIVIDER = {'type': 'divider'}

    def __init__(self, channel, user):
        self.channel = channel
        self.user = user
        self.icon_emoji = ':robot_face:'
        self.timestamp = ''
        self.completed = False

    def get_message(self):
        return {
            'ts': self.timestamp,
            'channel': self.channel,
            'username': 'Welcome Robot!',
            'icon_emoji': self.icon_emoji,
            'blocks': [
                self.START_TEXT,
                self.DIVIDER,
                self._get_reaction_task()
            ]
        }
    
    def _get_reaction_task(self):
        checkmark = ':white_check_mark:'
        if not self.completed:
            checkmark = ':white_large_square:'

        text = f'{checkmark} *React to this message!*'

        return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}}


#-------------------------------------------------------------------------
#Send Welcome Message
def send_welcome_message(channel, user):

    #Making sure it doesn't send tasks again
    if channel not in welcome_messages:
        welcome_messages[channel] = {}
    if user in welcome_messages[channel]:
        return

    welcome = WelcomeMessage(channel, user)
    message = welcome.get_message()
    response = client.chat_postMessage(**message) #** unpacks dictionaries
    welcome.timestamp = response['ts']

    if channel not in welcome_messages:
        welcome_messages[channel] = {}
    welcome_messages[channel][user] = welcome

#Scheduling Messages
def schedule_messages(messages):
    ids = []
    for msg in messages:
        response = client.chat_scheduleMessage(channel=msg['channel'], text=msg['text'], post_at=msg['post_at'])
        id_ = response.get('id')
        ids.append(id_)

    return ids

#Bad Words Checker
def bad_word_checker(message): 
    msg = message.lower()
    msg.translate(str.maketrans('', '', string.punctuation))

    return any(word in msg for word in BAD_WORDS) #if any of the bad words are in the message

#Setting up Message Payload into a channel
@slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    #Making sure bot responds to an actual user
    if user_id != None and BOT_ID != user_id:
        if user_id in message_counts: #Message Counter
            message_counts[user_id] += 1
        else:
            message_counts[user_id] = 1

        if text.lower() == 'start':
            send_welcome_message(f'@{user_id}', user_id)

        elif bad_word_checker(text): #Bad word checker implementation
            ts = event.get('ts')
            client.chat_postMessage(channel=channel_id, thread_ts=ts, text="That's a bad word homie.")


#Reactions
@slack_event_adapter.on('reaction_added')
def reaction(payload):
    event = payload.get('event', {})
    channel_id = event.get('item', {}).get('channel')
    user_id = event.get('user')

    #if welcome message wasn't in the channel
    if f'@{user_id}' not in welcome_messages:
        return
    
    welcome = welcome_messages[f'@{user_id}'][user_id]
    welcome.completed = True
    welcome.channel = channel_id
    message = welcome.get_message()
    updated_message = client.chat_update(**message)
    welcome.timestamp = updated_message['ts']


#Message Count Command
@app.route('/message-count', methods=['POST'])
def message_count():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    message_count = message_counts.get(user_id, 0)
    client.chat_postMessage(channel=channel_id, text=f"Messages: {message_count}")
    return Response(), 200 #return empty response 200 means OK it worked


#Taking Flash application and run on default port
#Debug says if you modify file u don't need to do the extra mile
if __name__ == "__main__":
    app.run(debug=True)
    schedule_messages(SCHEDULED_MESSAGES)