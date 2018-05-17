from apistar import http, App, Route
from boe import (
    get_boe_url,
    parse_boe,
    scrap_boe_items,
    search_words_in_boe
)
import datetime
import json
import os
import redis
import requests
import telebot
import threading
import time

TG_TOKEN = os.environ['TG_TOKEN']
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', False)
bot = telebot.TeleBot(TG_TOKEN)
db = redis.StrictRedis(host='redis', port=6379, db=0)


@bot.message_handler(commands=['start'])
def start_boe(message):
    words = db.get(message.from_user.id)
    if words is None or type(json.loads(words)) is not list:
        db.set(message.from_user.id, [])
        bot.reply_to(message, 'Ahora escribe /palabra y la palabra que quieras añadir para que el bot te notifique.')
    else:
        bot.reply_to(message, 'Ya estás registrado, te enviaremos notificaciones de las apariciones de tus palabras de búsqueda. Si quieres ver la lista de tus palabras de búsqueda puedes usar /lista.')


@bot.message_handler(commands=['palabra'])
def add(message):
    word = message.text.split('/palabra')[1]
    words = db.get(message.from_user.id)
    if words is None:
        bot.reply_to(message, 'Primero tienes que inicializar el bot utilizando /start')
        return
    if word == '':
        bot.reply_to(message, 'La forma de utilizarlo es enviar /palabra y despues la palabra que quieras buscar.')
        return

    word = word[1:]  # To remote tailing space
    words = json.loads(words)
    if word in words:
        bot.reply_to(message, 'Esa palabra ya está en tu lista de palabras de búsqueda.')
        return

    words.append(word)
    words = json.dumps(words)
    db.set(message.from_user.id, words)
    bot.reply_to(message, f'Tu palabra "{word}" se ha añadido a tu lista de palabras de búsqueda. Recuerda que si quieres añadir varias palabras debes añadirlas una a una, si pones espacios se buscará por la frase completa. Puedes usar /lista para ver todas las palabras de búsqueda que tienes o /borrar para borrar alguna de tus palabras de búsqueda.')


@bot.message_handler(commands=['lista'])
def ls(message):
    words = db.get(message.from_user.id)
    if words is None:
        bot.reply_to(message, 'Primero tienes que inicializar el bot utilizando /start')
        return
    words = json.loads(words)
    if len(words) is 0:
        bot.reply_to(message, 'No has añadido ninguna palabra de búsqueda. Usa /palabra para añadir palabras')
        return
    list_str = '\n'.join([f' - {word}' for word in words])
    bot.reply_to(message, f'Tu lista de palabras es:\n{list_str}')


@bot.message_handler(commands=['borrar'])
def delete_word_send(message):
    words = db.get(message.from_user.id)
    if words is None:
        bot.reply_to(message, 'Primero tienes que inicializar el bot utilizando /start')
        return

    words = json.loads(words)
    if len(words) is 0:
        bot.reply_to(message, 'No has añadido ninguna palabra de búsqueda aún. Usa /palabra para añadirlas.')
        return

    markup = telebot.types.ReplyKeyboardMarkup(row_width=2)
    for word in words:
        markup.add(telebot.types.KeyboardButton(word))
    bot.send_message(message.chat.id, 'Elige la palabra de búsqueda que quiere borrar', reply_markup=markup)


@bot.message_handler(commands=['check'])
def check_day(message):
    if message.text.split('/check')[1] == '':
        check_and_send_appearances(user=message.from_user.id)
    else:
        check_and_send_appearances(message.text.split('/check ')[1], user=message.from_user.id)


@bot.message_handler(func=lambda m: True)
def delete_word_receive(message):
    words = db.get(message.from_user.id)
    if words is None:
        bot.reply_to(message, 'Primero tienes que inicializar el bot utilizando /start')
        return

    word = message.text
    words = json.loads(words)
    if word not in words:
        bot.reply_to(message, f'La palabra "{word}" no está en tu lista de palabras de búsqueda. Si lo que quieres es añadirla, usa /palabra para añadirla')
        return

    words.remove(word)
    words = json.dumps(words)
    db.set(message.from_user.id, words)
    bot.reply_to(message, f'Tu palabra "{word}" ha sido eliminada')


def check_and_send_appearances(date=None, user=None):
    if user is None:
        users = [each.decode('utf-8') for each in db.keys()]
    else:
        users = [user]
    r = requests.get(get_boe_url(date))
    boe_items_empty = parse_boe(r.text)
    boe_items = scrap_boe_items(boe_items_empty)
    for user in users:
        words = json.loads(db.get(user))
        appearances = search_words_in_boe(words, boe_items)

    for a in appearances:
        if len(appearances[a]) is 1:
            message = f'La palabra {appearances[a][0]} aparece en el articulo "{a}". El PDF es {boe_items[a]["pdf"]}'
        else:
            message = f'Las palabras {", ".join(appearances[a])[::-1].replace(' ,', ' y ', 1)[::-1]} aparecen en el articulo "{a}". El PDF es {boe_items[a]["pdf"]}'

        bot.send_message(
            int(user),
            message
        )


def check_boe():
    while True:
        if datetime.datetime.now().hour is 8:
            check_and_send_appearances()
            time.sleep(36000)
        else:
            time.sleep(3600)


checker = threading.Thread(target=check_boe)
checker.start()


def set_webhook():
    webhook = bot.get_webhook_info()
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + "/bot")
    return '!'


def get_message(request: http.Request):
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.body.decode('utf-8'))])
    return '!'

if WEBHOOK_URL is False:
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=0, timeout=20)

routes = [
    Route('/', method='GET', handler=set_webhook),
    Route('/bot', method='POST', handler=get_message)
]
app = App(routes=routes)
