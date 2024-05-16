from peewee import *
import telebot
from telebot import types
import random

# Настройка базы данных
db = PostgresqlDatabase('postgres', user='postgres', password='postgres', host='localhost', port=5432)

class Group(Model):
    name = CharField(unique=True)
    description = TextField(null=True)
    class Meta:
        database = db

class Photo(Model):
    user_id = IntegerField()
    photo_id = TextField()
    group = ForeignKeyField(Group, backref='photos', null=True)
    class Meta:
        database = db

class Vote(Model):
    photo = ForeignKeyField(Photo, backref='votes')
    user_id = IntegerField()
    vote = IntegerField(default=0)  # Счётчик голосов
    class Meta:
        database = db

# Соединяемся с базой данных
db.connect()
# db.drop_tables([Photo, Group, Vote], safe=True, cascade=True)
db.create_tables([Group, Photo, Vote], safe=True)

# Токен бота
TOKEN = '6544292556:AAHKZOH7XC3d0y2dh4fJsggza7SP_unJtWw'
bot = telebot.TeleBot(TOKEN)

# Приветственное сообщение
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_upload = types.KeyboardButton('Загрузить фото')
    btn_rate = types.KeyboardButton('Оценить')
    markup.add(btn_upload, btn_rate)
    bot.send_message(message.chat.id, "Привет! Вы можете загрузить фото или оценить уже загруженные.", reply_markup=markup)
@bot.message_handler(func=lambda message: message.text == 'Загрузить фото')
def handle_text(message):
    groups = Group.select()
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    for group in groups:
        markup.add(types.KeyboardButton(group.name))
    markup.add(types.KeyboardButton('Создать новую группу'))
    msg = bot.send_message(message.chat.id, "Выберите группу или создайте новую.", reply_markup=markup)
    bot.register_next_step_handler(msg, photo_upload)

def photo_upload(message):
    if message.text == 'Создать новую группу':
        msg = bot.send_message(message.chat.id, "Введите название для новой группы:")
        bot.register_next_step_handler(msg, create_group)
    else:
        # Проверяем, существует ли группа
        try:
            group = Group.get(Group.name == message.text)
        except Group.DoesNotExist:
            # Если группа не найдена, сообщаем пользователю и возвращаемся к выбору группы
            bot.send_message(message.chat.id, "Группа не найдена, пожалуйста, выберите группу еще раз.")
            handle_text(message)  # Повторно вызываем функцию для выбора группы
            return

        # Если группа найдена, просим отправить фото
        msg = bot.send_message(message.chat.id, "Отправьте фото для группы " + group.name)
        bot.register_next_step_handler(msg, lambda msg: handle_photos(msg, group))


def create_group(message):
    group_name = message.text
    group, created = Group.get_or_create(name=group_name)
    if created:
        response = "Группа создана. Теперь вы можете загрузить фото в эту группу."
    else:
        response = "Группа с таким названием уже существует."

    # Отправка сообщения о статусе создания группы
    bot.send_message(message.chat.id, response)

    # Обновление или повторное отправление основного меню
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_upload = types.KeyboardButton('Загрузить фото')
    btn_rate = types.KeyboardButton('Оценить')
    markup.add(btn_upload, btn_rate)
    bot.send_message(message.chat.id, "Выберите действие.", reply_markup=markup)


def handle_photos(message, group):
    if 'photo' in message.content_type:
        photo_id = message.photo[-1].file_id
        Photo.create(user_id=message.from_user.id, photo_id=photo_id, group=group)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_upload = types.KeyboardButton('Загрузить фото')
        btn_rate = types.KeyboardButton('Оценить')
        markup.add(btn_upload, btn_rate)
        bot.send_message(message.chat.id, "Фото сохранено в группу " + group.name + "!", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == 'Оценить')
def handle_rating(message):
    photos = list(Photo.select().where(Photo.group.is_null(False)))
    if len(photos) < 2:
        bot.send_message(message.chat.id, "Недостаточно фотографий для оценки.")
        return

    random_photos = random.sample(photos, 2)
    media_group = [
        types.InputMediaPhoto(random_photos[0].photo_id, caption="Фото 1"),
        types.InputMediaPhoto(random_photos[1].photo_id, caption="Фото 2")
    ]

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('Голосовать за фото 1', callback_data=f'vote_{random_photos[0].id}')
    btn2 = types.InlineKeyboardButton('Голосовать за фото 2', callback_data=f'vote_{random_photos[1].id}')
    markup.add(btn1, btn2)

    bot.send_media_group(message.chat.id, media_group)
    bot.send_message(message.chat.id, "Выберите лучшее фото:", reply_markup=markup)  # Отправляем сообщение с инлайн клавиатурой после фото



@bot.callback_query_handler(func=lambda call: call.data.startswith('vote_'))
def handle_vote(call):
    photo_id = int(call.data.split('_')[1])
    photo = Photo.get_by_id(photo_id)
    Vote.create(photo=photo, user_id=call.from_user.id, vote=1)
    bot.answer_callback_query(call.id, f"Вы проголосовали за фото {photo_id}.")
    update_photo_rating(photo_id)

def update_photo_rating(photo_id):
    photo = Photo.get_by_id(photo_id)
    total_votes = sum(v.vote for v in photo.votes)
    bot.send_message(chat_id=call.message.chat.id, text=f"Текущий рейтинг фото {photo_id}: {total_votes} голосов.")

bot.infinity_polling()