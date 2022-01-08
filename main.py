#!/usr/bin/python3

import logging
import time
from datetime import datetime

from pymongo import MongoClient
import docker
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import Bot

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

docker_client = docker.from_env()
mc = docker_client.containers.get('mc')

mongo_client = MongoClient()
db = mongo_client.mcbot
chats = db.chats

TOKEN='yourbottoken'
bot = Bot(token=TOKEN)  # ticks to seconds

TTS = 24 * 60 * 60 / 24000

players = { #set of player names
}
def start(update, context):
    update.message.reply_text('Hi!')

def register(update, context):
    """Usage: /register BOT_SECRET_KEY"""
    key = update.message.text.partition(' ')[2]
    if key != 'botpassword':  # password so others can'` use your bot and read chat:
        update.message.reply_text('Wrong Key')
        return

    print(f'Successful register got chat_id: {update.message.chat_id}')
    doc = chats.update_one({'_id': update.message.chat_id},
                     {'$set': {
                        'register': True,
                        'subscriptions': ['chat', 'log']}
                      },
                     upsert=True,
                     #new=True
                     )
    print(f'Upsert: {dict(doc)}')
    update.message.reply_text('Welcome to the my MineCraft server!')

def echo(update, context):
    doc = chats.find_one({'_id': update.message.chat_id})
    if not doc:
        update.message.reply_text('You are not a member')
        return
    from_user = update.message.from_user
    user = from_user.username or ' '.join([from_user.first_name, from_user.last_name])
    mc.exec_run(f'rcon-cli say \'<{user}> {update.message.text}\'') #text can be 'None' if you send picture or else to tg. Leave this so you can open tg and check
                
def get_time(update, context):
    doc = chats.find_one({'_id': update.message.chat_id})
    if not doc:
        update.message.reply_text('You are not a member')
        return
    from_user = update.message.from_user
    mc_daytime = mc.exec_run('rcon-cli time query daytime')
    ticks = int(mc_daytime.output.decode().strip()[12:])
    seconds = datetime.fromtimestamp(ticks * TTS + 6 * 60 * 60)
    t = datetime.strftime(seconds, '%H:%M')
    update.message.reply_text(t)
        
def list_online(update, context):
    doc = chats.find_one({'_id': update.message.chat_id})
    if not doc:
        update.message.reply_text('You are not a member')
        return
    r = mc.exec_run('rcon-cli list')
    update.message.reply_text(r.output.decode().strip())

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def splitter(file):
    current = []
    for line in file:
        line = line.decode().strip()
        if line.startswith('['):
            if current:
                yield ' '.join(current)
            current = [line]
        else:
            current.append(line)
    yield ' '.join(current)

deaths = set([  # for 1.16
    'was shot by',
    'was pricked to death',
    'walked into',
    'drowned',
    'experienced kinetic energy',
    'blew up',
    'was blown up by',
    'was killed by',
    'hit the ground too hard',
    'fell from a high place',
    'fell off',
    'was squashed by a falling anvil',
    'was squashed by a falling block',
    'went up in flames',
    'burned to death',
    'was burnt to a crisp whilst fighting',
    'went off with a bang',
    'tried to swim in lava',
    'was struck by lightning',
    'discovered the floor was lava',
    'was killed ',
    'was slain by',
    'was fireballed by',
    'was stung to death',
    'was pummeled by',
    'starved to death',
    'suffocated in a wall',
    'was squished',
    'was poked to death by a sweet berry bush',
    'was impaled',
    'fell out of the world',
    'didn\'t want to live in the same world as',
    'withered away',
])

log_in = set(['joined the game'])
log_out = set(['left the game'])

ads = set(['advancement', 'challenge'])

def process_line(line):
    line = line[33:]

    if any(msg in line for msg in log_in):
        return line, 'log'
    if any(msg in line for msg in log_out):
        return line, 'log'
    if any(msg in line for msg in ads):
        return line, 'ads'
    if any(msg in line for msg in deaths):
        return line, 'death'
    if any(line.startswith(f'<{player}>') for player in players):
        return line, 'chat'
    
    return None, None
 

def main():
    updater = Updater(TOKEN, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("register", register))
    dp.add_handler(CommandHandler("list", list_online))
    dp.add_handler(CommandHandler("time", get_time))
    dp.add_handler(MessageHandler(Filters.text | Filters.group, echo))
    
    dp.add_error_handler(error)

    updater.start_polling()
    for entry in mc.logs(since=int(time.time()), stream=True):
        line, msg_type  = process_line(entry.decode())
        if not line:
            continue
        for doc in chats.find({'register': True}):
            bot.send_message(chat_id=doc['_id'], text=line)

if __name__ == '__main__':
    main()
