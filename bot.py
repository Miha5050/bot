from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import datetime
import pytz
import random
import asyncio
import os
import requests
from threading import Thread
import time
from flask import Flask

# ========== НАСТРОЙКИ ДЛЯ RENDER ==========
BOT_TOKEN = os.getenv('BOT_TOKEN')
RENDER_URL = os.getenv('RENDER_URL')
PORT = int(os.getenv('PORT', 10000))

# Проверка обязательных переменных
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не установлен!")
    print("ℹ️ Установите переменную BOT_TOKEN в настройках Render")
    exit(1)

if not RENDER_URL:
    print("⚠️ ПРЕДУПРЕЖДЕНИЕ: RENDER_URL не установлен")
    print("ℹ️ Установите переменную RENDER_URL для анти-засыпания")

# Конфигурация бота
class BotConfig:
    TIMEZONE = pytz.timezone('Asia/Yekaterinburg')
    CHECK_INTERVAL = 300  # 5 минут

# ========== ФУНКЦИИ ДЛЯ АНТИ-ЗАСЫПАНИЯ ==========

def keep_alive_pinger():
    """Пингет сервер каждые 10 минут чтобы не засыпал на Render"""
    if not RENDER_URL:
        print("❌ Анти-засыпание отключено: RENDER_URL не установлен")
        return
        
    print("🔄 Запуск анти-засыпания...")
    while True:
        try:
            response = requests.get(RENDER_URL, timeout=10)
            print(f"✅ Пинг отправлен в {datetime.datetime.now().strftime('%H:%M:%S')} - статус: {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка пинга: {e}")
        
        # Ждем 10 минут (600 секунд)
        time.sleep(600)

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========

web_app = Flask(__name__)

@web_app.route('/')
def home():
    current_time = datetime.datetime.now(BotConfig.TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
    return f"""
    <h1>🤖 Telegram Bot Active</h1>
    <p><strong>Статус:</strong> ✅ Работает нормально</p>
    <p><strong>Время сервера:</strong> {current_time}</p>
    <p><strong>Часовой пояс:</strong> Екатеринбург</p>
    <p><strong>Последняя проверка:</strong> Каждые 5 минут</p>
    <hr>
    <p>Бот от: @Miha5050</p>
    """

@web_app.route('/health')
def health_check():
    """Эндпоинт для проверки здоровья"""
    return "OK", 200

def run_web_server():
    """Запускает веб-сервер для Render"""
    print(f"🌐 Запуск веб-сервера на порту {PORT}")
    web_app.run(host='0.0.0.0', port=PORT, debug=False)

# ========== ОСНОВНЫЕ ФУНКЦИИ БОТА ==========

def generate_motivational_quote():
    quotes = [
        "Каждый день — это новый шанс стать лучше!",
        "Верь в себя, и ты будешь неудержим!",
        "Твои мечты стоят того, чтобы за них бороться.",
        "Не сдавайся — великие дела требуют времени.",
        "Успех — это сумма маленьких усилий, повторяемых изо дня в день.",
        "Ты способен на большее, чем думаешь!",
        "Ошибки — это ступени к успеху.",
        "Начни там, где ты есть. Используй то, что у тебя есть. Делай что можешь.",
        "Сегодняшние трудности завтра станут твоей силой.",
        "Действие — ключевой элемент успеха.",
        "Ты ближе к цели, чем был вчера.",
        "Позитивное мышление привлекает позитивные результаты.",
        "Твоё время пришло! Действуй без промедлений.",
        "Никогда не недооценивай себя. Ты уникален!",
        "Самый простой способ добиться успеха — никогда не сдаваться."
    ]
    return random.choice(quotes)

def create_poem():
    adjectives = ["заботливая", "мудрая", "прекрасная", "добрая", "умная", "организованная"]
    actions = ["учила", "вдохновляла", "поддерживала", "воспитывала"]
    memories = ["путешествий", "учёбы", "отдыха", "трудностей"]
    my_memories = ["научила меня читать", "записала меня на шахматы", "записала меня в кванториум", "сводила меня в галлилео", "скачала мне фильм жил был человек"]

    poem = f"""
    Дорогая мама, ты такая {random.choice(adjectives)},
    Ты всегда меня {random.choice(actions)} во время {random.choice(memories)}.
    Помню, как ты {random.choice(my_memories)}
    Спасибо за всё! Люблю тебя больше всего на свете!
    """
    return poem

def is_exact_time(target_hour, target_minute):
    """Проверяет совпадение времени с учетом допустимого отклонения в 5 минут"""
    now = datetime.datetime.now(BotConfig.TIMEZONE)
    current_total_minutes = now.hour * 60 + now.minute
    target_total_minutes = target_hour * 60 + target_minute
    
    return abs(current_total_minutes - target_total_minutes) <= 5

# Глобальные переменные
daily = "включены"
users_for_daily = set()
user_notes = {}
user_reminders = {}
morning_time = (9, 0)
evening_time = (18, 0)
last_morning_notification = None
last_evening_notification = None

def get_main_keyboard():
    global daily
    keyboard = [
        ["📝 заметки", "🔔 напоминания"],
        ["✍️ хочу интересную фразу"],
        ["❓помощь"],
        [f"ежедневные сообщения {daily}"]  
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

async def send_morning_message(app: Application):
    """Отправляет утреннее сообщение всем подписанным пользователям"""
    global last_morning_notification
    
    current_time = datetime.datetime.now(BotConfig.TIMEZONE)
    today = current_time.date()
    
    if daily == "включены" and users_for_daily and last_morning_notification != today:
        message = f"🌅 Доброе утро! Хорошего дня! 🌞\n\n{generate_motivational_quote()}"
        for chat_id in users_for_daily:
            try:
                await app.bot.send_message(chat_id=chat_id, text=message)
                print(f"✅ Утреннее сообщение отправлено пользователю {chat_id}")
            except Exception as e:
                print(f"❌ Ошибка отправки пользователю {chat_id}: {e}")
        
        last_morning_notification = today
        print(f"📅 Запомнена дата утреннего уведомления: {today}")

async def send_evening_message(app: Application):
    """Отправляет вечернее сообщение со стихотворением"""
    global last_evening_notification
    
    current_time = datetime.datetime.now(BotConfig.TIMEZONE)
    today = current_time.date()
    
    if daily == "включены" and users_for_daily and last_evening_notification != today:
        # Создаем вечернее сообщение со стихотворением
        message = f"""🌃 Добрый вечер! 🌙

{create_poem()}

💫 Пусть этот вечер принесет умиротворение и приятные мысли!"""
        
        for chat_id in users_for_daily:
            try:
                await app.bot.send_message(chat_id=chat_id, text=message)
                print(f"✅ Вечернее сообщение со стихотворением отправлено пользователю {chat_id}")
            except Exception as e:
                print(f"❌ Ошибка отправки пользователю {chat_id}: {e}")
        
        last_evening_notification = today
        print(f"📅 Запомнена дата вечернего уведомления: {today}")

async def check_reminders(app: Application):
    """Проверка напоминаний"""
    current_time = datetime.datetime.now(BotConfig.TIMEZONE)
    print(f"🔔 Проверка напоминаний: {current_time.strftime('%H:%M:%S')}")
    
    for user_id in list(user_reminders.keys()):
        if user_id not in user_reminders:
            continue
            
        reminders = user_reminders[user_id]
        
        for i in range(len(reminders)):
            if user_id not in user_reminders or i >= len(user_reminders[user_id]):
                break
                
            reminder = user_reminders[user_id][i]
            hours = reminder["hours"]
            minutes = reminder["minutes"]
            text = reminder["text"]
            
            if is_exact_time(hours, minutes):
                try:
                    if (user_id in user_reminders and 
                        i < len(user_reminders[user_id]) and
                        user_reminders[user_id][i]["hours"] == hours and
                        user_reminders[user_id][i]["minutes"] == minutes and
                        user_reminders[user_id][i]["text"] == text):
                        
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=f"🔔 Напоминание!\n\n{text}"
                        )
                        print(f"✅ Напоминание отправлено пользователю {user_id}")
                        
                except Exception as e:
                    print(f"❌ Ошибка отправки напоминания: {e}")

async def check_time_and_notify(app: Application):
    """Асинхронная проверка времени и отправка уведомлений"""
    current_time = datetime.datetime.now(BotConfig.TIMEZONE)
    print(f"⏰ Проверка времени: {current_time.strftime('%H:%M:%S')}")
    
    # Проверяем утренние уведомления
    if is_exact_time(morning_time[0], morning_time[1]):
        print("🔔 Условие для утреннего уведомления выполнено")
        await send_morning_message(app)
    else:
        print(f"❌ Утреннее уведомление: текущее время {current_time.strftime('%H:%M')}, целевое {morning_time[0]:02d}:{morning_time[1]:02d}")
        
    # Проверяем вечерние уведомления
    if is_exact_time(evening_time[0], evening_time[1]):
        print("🔔 Условие для вечернего уведомления выполнено")
        await send_evening_message(app)
    else:
        print(f"❌ Вечернее уведомление: текущее время {current_time.strftime('%H:%M')}, целевое {evening_time[0]:02d}:{evening_time[1]:02d}")
    
    # Проверяем напоминания
    await check_reminders(app)
    
    print("✅ Все проверки завершены")

def start_time_checker(app: Application):
    """Запускает асинхронную проверку времени каждые 5 минут"""
    async def time_checker_loop():
        print("🕒 Запуск планировщика проверок с интервалом 5 минут")
        while True:
            try:
                await check_time_and_notify(app)
            except Exception as e:
                print(f"❌ Ошибка в проверке времени: {e}")
            
            # Ждем 5 минут (300 секунд) до следующей проверки
            print("⏳ Ожидание 5 минут до следующей проверки...")
            await asyncio.sleep(300)
    
    loop = asyncio.get_event_loop()
    loop.create_task(time_checker_loop())

# ========== КОМАНДЫ БОТА ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - показывает клавиатуру"""
    users_for_daily.add(update.effective_chat.id)
    
    welcome_text = (
        "👋 Привет!\n\n"
        "Я бот от пользователя @Miha5050\n\n"
        "вы можете зажать подсказку для команды чтобы ею воспользоваться.\n\n"        
        "Используйте кнопки ниже для управления ботом:"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /set_time - установить время утренних и вечерних уведомлений"""
    global morning_time, evening_time
    
    if context.args and len(context.args) == 4:
        try:
            morning_hours = int(context.args[0])
            morning_minutes = int(context.args[1])
            evening_hours = int(context.args[2])
            evening_minutes = int(context.args[3])
            
            if (0 <= morning_hours <= 23 and 0 <= morning_minutes <= 59 and
                0 <= evening_hours <= 23 and 0 <= evening_minutes <= 59):
                
                morning_time = (morning_hours, morning_minutes)
                evening_time = (evening_hours, evening_minutes)
                
                await update.message.reply_text(
                    f"✅ Время уведомлений установлено!\n\n"
                    f"🌅 Утренние уведомления: {morning_hours:02d}:{morning_minutes:02d}\n"
                    f"🌃 Вечерние уведомления: {evening_hours:02d}:{evening_minutes:02d}\n\n"
                    f"Уведомления будут отправляться в указанное время ±5 минут"
                )
            else:
                await update.message.reply_text("❌ Неверное время! Часы: 0-23, Минуты: 0-59")
                
        except ValueError:
            await update.message.reply_text("❌ Используйте: /set_time <утро_часы> <утро_минуты> <вечер_часы> <вечер_минуты>")
    else:
        await update.message.reply_text(
            f"⏰ Текущее время уведомлений:\n\n"
            f"🌅 Утренние: {morning_time[0]:02d}:{morning_time[1]:02d}\n"
            f"🌃 Вечерние: {evening_time[0]:02d}:{evening_time[1]:02d}\n\n"
            f"Установите новое время:\n"
            f"/set_time <утро_часы> <утро_минуты> <вечер_часы> <вечер_минуты>\n\n"
            f"Пример: /set_time 9 0 18 0"
        )

async def create_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для создания заметки"""
    chat_id = update.effective_chat.id
    
    if context.args:
        note_text = ' '.join(context.args)
        
        if chat_id not in user_notes:
            user_notes[chat_id] = []
        
        user_notes[chat_id].append(note_text)
        await update.message.reply_text(f"✅ Заметка создана!\n\n📝 Текст: {note_text}")
    else:
        if chat_id in user_notes and user_notes[chat_id]:
            notes_list = "\n".join([f"{i+1}. {note}" for i, note in enumerate(user_notes[chat_id])])
            await update.message.reply_text(f"📋 Ваши заметки:\n\n{notes_list}")
        else:
            await update.message.reply_text("📝 У вас пока нет заметок.\n\nИспользуйте: /create_note <текст>")

async def delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для удаления заметки"""
    chat_id = update.effective_chat.id
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("❌ Используйте: /delete_note <номер заметки>")
        return
    
    try:
        note_index = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("❌ Номер заметки должен быть числом.")
        return
    
    if chat_id not in user_notes or not user_notes[chat_id]:
        await update.message.reply_text("📝 У вас пока нет заметок для удаления.")
        return
    
    if note_index < 0 or note_index >= len(user_notes[chat_id]):
        await update.message.reply_text(f"❌ Неверный номер заметки. У вас есть заметки с 1 по {len(user_notes[chat_id])}.")
        return
    
    deleted_note = user_notes[chat_id].pop(note_index)
    await update.message.reply_text(f"✅ Заметка удалена:\n\n📝 {deleted_note}")

async def create_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание напоминания"""
    user_id = update.effective_chat.id
    
    if context.args and len(context.args) >= 3:
        try:
            hours = int(context.args[0])
            minutes = int(context.args[1])
            reminder_text = ' '.join(context.args[2:])
            
            if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                await update.message.reply_text("❌ Неверное время! Часы: 0-23, Минуты: 0-59")
                return
            
            if user_id not in user_reminders:
                user_reminders[user_id] = []
            
            user_reminders[user_id].append({
                "hours": hours,
                "minutes": minutes,
                "text": reminder_text
            })
            
            reminder_number = len(user_reminders[user_id])
            
            await update.message.reply_text(
                f"✅ Напоминание создано!\n\n"
                f"🔔 Номер: {reminder_number}\n"
                f"⏰ Время: {hours:02d}:{minutes:02d}\n"
                f"📝 Текст: {reminder_text}\n\n"
                f"Чтобы удалить: /delete_reminder {reminder_number}"
            )
            print(f"✅ Напоминание #{reminder_number} создано для пользователя {user_id}")
            
        except ValueError:
            await update.message.reply_text("❌ Ошибка: часы и минуты должны быть числами")
    else:
        await update.message.reply_text(
            "❌ Используйте: /create_reminder <часы> <минуты> <текст>\n\n"
            "Пример: /create_reminder 9 30 Позвонить маме"
        )

async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление напоминания"""
    user_id = update.effective_chat.id
    
    if context.args and len(context.args) == 1:
        try:
            reminder_number = int(context.args[0]) - 1
            
            if (user_id not in user_reminders or 
                reminder_number < 0 or 
                reminder_number >= len(user_reminders[user_id])):
                await update.message.reply_text("❌ Напоминание с таким номером не найдено.")
                return
            
            removed_reminder = user_reminders[user_id].pop(reminder_number)
            
            if not user_reminders[user_id]:
                del user_reminders[user_id]
            
            await update.message.reply_text(
                f"✅ Напоминание удалено!\n\n"
                f"🔔 Номер: {reminder_number + 1}\n"
                f"⏰ Время: {removed_reminder['hours']:02d}:{removed_reminder['minutes']:02d}\n"
                f"📝 Текст: {removed_reminder['text']}"
            )
            print(f"🗑️ Напоминание #{reminder_number + 1} удалено для пользователя {user_id}")
            
        except ValueError:
            await update.message.reply_text("❌ Номер напоминания должен быть числом.")
    else:
        await update.message.reply_text("❌ Используйте: /delete_reminder <номер напоминания>")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список напоминаний"""
    user_id = update.effective_chat.id
    
    if user_id in user_reminders and user_reminders[user_id]:
        reminders_list = []
        for i, reminder_data in enumerate(user_reminders[user_id]):
            reminders_list.append(
                f"🔔 {i+1}. В {reminder_data['hours']:02d}:{reminder_data['minutes']:02d}\n"
                f"   📝 {reminder_data['text']}"
            )
        
        response = "📋 Ваши напоминания:\n\n" + "\n".join(reminders_list)
        response += "\n\n💡 Чтобы удалить напоминание: /delete_reminder <номер>"
    else:
        response = (
            "🔔 У вас пока нет напоминаний.\n\n"
            "Чтобы создать напоминание, используйте:\n"
            "/create_reminder <часы> <минуты> <текст>\n\n"
            "Пример: /create_reminder 9 30 Позвонить маме"
        )
    
    await update.message.reply_text(response)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    global daily
    user_text = update.message.text
    chat_id = update.effective_chat.id

    if user_text == "✍️ хочу интересную фразу":
        response = f"{create_poem()}\n\ncreate by random"
    
    elif user_text == "📝 заметки":
        if chat_id in user_notes and user_notes[chat_id]:
            notes_list = "\n".join([f"{i+1}. {note}" for i, note in enumerate(user_notes[chat_id])])
            response = f"📋 Ваши заметки:\n\n{notes_list}"
        else:
            response = "📝 У вас пока нет заметок."
    
    elif user_text == "🔔 напоминания":
        await list_reminders(update, context)
        return

    elif user_text == "❓помощь":
        response = (
            "ℹ️ Доступные команды:\n\n"
            "📝 ЗАМЕТКИ:\n"
            "/create_note <текст> - Создать заметку\n"
            "/delete_note <номер> - Удалить заметку\n\n"
            "🔔 НАПОМИНАНИЯ:\n"
            "/create_reminder <часы> <минуты> <текст> - Создать напоминание\n"
            "/delete_reminder <номер> - Удалить напоминание\n"
            "/list_reminders - Показать все напоминания\n\n"
            "⚙️ ОБЩИЕ:\n"
            "/start - Показать клавиатуру\n"
            "/help - Показать справку\n"
            "/set_time - Установить время уведомлений\n\n"
            "Или используйте кнопки ниже:"
        )
    
    elif user_text.startswith("ежедневные сообщения"):
        if daily == "включены":
            daily = "отключены"
            if chat_id in users_for_daily:
                users_for_daily.remove(chat_id)
            response = "Ежедневные сообщения отключены!"
        else:
            daily = "включены"
            users_for_daily.add(chat_id)
            response = "Ежедневные сообщения включены!"
        
        await update.message.reply_text(response, reply_markup=get_main_keyboard())
        return
    
    else:
        response = "Пожалуйста, используйте кнопки для навигации"

    await update.message.reply_text(response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "ℹ️ Доступные команды:\n\n"
        "📝 ЗАМЕТКИ:\n"
        "/create_note <текст> - Создать заметку\n"
        "/delete_note <номер> - Удалить заметку\n\n"
        "🔔 НАПОМИНАНИЯ:\n"
        "/create_reminder <часы> <минуты> <текст> - Создать напоминание\n"
        "/delete_reminder <номер> - Удалить напоминание\n"
        "/list_reminders - Показать все напоминания\n\n"
        "⚙️ ОБЩИЕ:\n"
        "/start - Показать клавиатуру\n"
        "/help - Показать справку\n"
        "/set_time - Установить время уведомлений\n\n"
        "Или используйте кнопки ниже:"
    )
    await update.message.reply_text(help_text)

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========

def main():
    print("🟢 Запуск бота...")
    print(f"✅ BOT_TOKEN: {'установлен' if BOT_TOKEN else 'НЕ УСТАНОВЛЕН'}")
    print(f"🌐 RENDER_URL: {RENDER_URL or 'не установлен'}")
    print(f"⏰ Часовой пояс: Екатеринбург")
    
    # Запускаем анти-засыпание в отдельном потоке
    if RENDER_URL:
        pinger_thread = Thread(target=keep_alive_pinger, daemon=True)
        pinger_thread.start()
        print("🔄 Анти-засыпание: активировано")
    else:
        print("⚠️ Анти-засыпание: отключено (RENDER_URL не установлен)")
    
    # Запускаем веб-сервер в отдельном потоке
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print(f"🌐 Веб-сервер: запущен на порту {PORT}")
    
    # Инициализируем бота
    bot_app = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("help", help_command))
    bot_app.add_handler(CommandHandler("set_time", set_time_command))
    bot_app.add_handler(CommandHandler("create_note", create_note))
    bot_app.add_handler(CommandHandler("delete_note", delete_note))
    bot_app.add_handler(CommandHandler("create_reminder", create_reminder))
    bot_app.add_handler(CommandHandler("delete_reminder", delete_reminder))
    bot_app.add_handler(CommandHandler("list_reminders", list_reminders))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    # Запускаем планировщик
    start_time_checker(bot_app)

    print("✅ Все системы запущены!")
    print("🔔 Проверки каждые 5 минут")
    
    # Запускаем бота
    bot_app.run_polling()

if __name__ == "__main__":
    main()