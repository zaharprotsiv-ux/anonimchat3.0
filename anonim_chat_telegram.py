from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread
import os
import logging


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "8461312515:AAGeeXobVBY04d8TduNVunfQsfz19hu-frc"


pairs = {}          # {user_id: partner_id, partner_id: user_id}
waiting_user = None # ID користувача, який очікує на підключення



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє команду /start."""
    await update.message.reply_text(
        "👋 Привіт! Я анонімний чат-бот.\n"
        "Напиши /find, щоб знайти співрозмовника.\n"
        "Напиши /stop, щоб завершити чат."
    )

async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє команду /find та з'єднує користувачів."""
    global waiting_user
    user_id = update.message.from_user.id
    
   
    if user_id in pairs:
        await update.message.reply_text("Ти вже в чаті. Напиши /stop, щоб завершити поточний чат.")
        return
    
  
    if user_id == waiting_user:
        await update.message.reply_text("Ти вже шукаєш співрозмовника. Будь ласка, зачекай.")
        return

    # 3. Логіка пошуку та підключення
    if waiting_user is not None:
        # Знайдено пару!
        partner_id = waiting_user
        
        # Перевірка, щоб не підключити до самого себе (хоча це малоймовірно, якщо логіка вірна)
        if partner_id == user_id:
            await update.message.reply_text("Помилка: Спроба підключитися до самого себе. Спробуй ще раз.")
            waiting_user = None
            return

        # Створення пари
        pairs[user_id] = partner_id
        pairs[partner_id] = user_id
        waiting_user = None # Список очікування тепер порожній

        # Сповіщення обох користувачів
        await context.bot.send_message(partner_id, "✅ Знайдено співрозмовника! Можна писати!")
        await update.message.reply_text("✅ Знайдено співрозмовника! Можна писати!")
        logger.info(f"З'єднано: {user_id} та {partner_id}")

    else:
        # Якщо ніхто не чекає, ставимо користувача в очікування
        waiting_user = user_id
        await update.message.reply_text("🔍 Шукаю співрозмовника... Зачекай, будь ласка.")
        logger.info(f"Користувач {user_id} очікує.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє команду /stop та розриває з'єднання."""
    global waiting_user
    user_id = update.message.from_user.id
    
    # 1. Якщо користувач очікував
    if user_id == waiting_user:
        waiting_user = None
        await update.message.reply_text("🚫 Ти припинив пошук співрозмовника.")
        logger.info(f"Користувач {user_id} скасував очікування.")
        return

    # 2. Якщо користувач у чаті
    if user_id in pairs:
        partner_id = pairs[user_id]
        
        # Видаляємо обидва записи з пар
        del pairs[user_id]
        if partner_id in pairs:
            del pairs[partner_id]
            
        # Сповіщення партнера
        await context.bot.send_message(partner_id, "🚫 Твій співрозмовник завершив чат. Напиши /find, щоб почати новий пошук.")
        await update.message.reply_text("✅ Ти завершив чат. Напиши /find, щоб знайти нового співрозмовника.")
        logger.info(f"Чат завершено між {user_id} та {partner_id}")
        return
        
    # 3. Якщо користувач ніде не був
    await update.message.reply_text("🤔 Ти зараз не в чаті і не в пошуку.")

async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересилає повідомлення між партнерами."""
    user_id = update.message.from_user.id
    
    # Перевіряємо, чи є користувач у чаті
    if user_id not in pairs:
        await update.message.reply_text("Ти не в чаті. Напиши /find, щоб знайти співрозмовника.")
        return

    partner_id = pairs[user_id]
    
    # Використовуємо вбудовану функцію forward_message для кращої підтримки всіх типів медіа
    try:
        await context.bot.forward_message(
            chat_id=partner_id,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"Помилка пересилання повідомлення від {user_id} до {partner_id}: {e}")
        await update.message.reply_text("Помилка: не вдалося переслати повідомлення.")


# ====== Вебсервер для UptimeRobot ======
# Цей код забезпечує роботу 24/7
web_app = Flask('')

@web_app.route('/')
def home():
    """Endpoint, який пінгує UptimeRobot."""
    return "Telegram Bot працює!"

def run_web():
    """Запускає веб-сервер Flask."""
    # Replit встановлює порт через змінну середовища PORT
    port = int(os.environ.get("PORT", 3000))
    web_app.run(host='0.0.0.0', port=port)

# ====== Основна функція ======
def main():
    """Ініціалізує та запускає бота і веб-сервер."""
    logger.info("Починаємо ініціалізацію...")
    
    # 1. Запускаємо вебсервер у окремому потоці для UptimeRobot
    t = Thread(target=run_web, daemon=True) # daemon=True дозволяє потоку закритися при завершенні main
    t.start()
    logger.info("Веб-сервер для UptimeRobot запущено.")

    # 2. Telegram бот
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Додавання обробників
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))
    app.add_handler(CommandHandler("stop", stop))
    
    # Обробник для всіх інших повідомлень (текст, фото, відео, аудіо, документ)
    # Використовуємо filters.ALL & ~filters.COMMAND
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, relay_message))

    logger.info("Бот запущено і слухає оновлення (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()