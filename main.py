import re
import telebot
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask, request
import os

# Apna real bot token daal do
BOT_TOKEN = '6995849427:AAG1ijDaJzWilqDpU1fM8mGALjXctWXzDHg'  # @BotFather se token lo
API_BASE_URL = 'https://socialdownloder2.anshapi.workers.dev/?url='

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

SOCIAL_MEDIA_PATTERNS = re.compile(
    r"(https?:\/\/(?:www\.)?(?:youtube\.com|youtu\.be|instagram\.com|facebook\.com|fb\.watch|twitter\.com|x\.com|tiktok\.com|threads\.net|pinterest\.com|reddit\.com)[^\s]*)",
    re.IGNORECASE
)

user_data = {}

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "Hey! 👋 Koi bhi social media video URL (YouTube, Instagram, etc.) bhejo, main download links dunga! 📥")

@bot.message_handler(func=lambda message: True)
def handle_url(message):
    url_match = SOCIAL_MEDIA_PATTERNS.search(message.text.strip())
    if not url_match:
        return

    url = url_match.group(0)
    bot.send_chat_action(message.chat.id, "typing")

    api_url = API_BASE_URL + url
    try:
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()
        medias = data.get('medias', [])
        title = data.get('title', 'Video')
        thumbnail = data.get('thumbnail')

        if not medias:
            bot.reply_to(message, "❌ Koi download links nahi mile! URL check karo.")
            return

        song_link = None
        video_link = None
        for media in medias:
            if 'audio' in media.get('type', '').lower():
                song_link = media.get('url')
            elif 'video' in media.get('type', '').lower():
                video_link = media.get('url')

        if not song_link and not video_link:
            bot.reply_to(message, "❌ Koi valid media nahi mila!")
            return

        user_data[message.chat.id] = {
            "song": song_link,
            "video": video_link,
            "title": title,
            "thumbnail": thumbnail
        }

        send_main_message(message.chat.id)

    except requests.exceptions.RequestException as e:
        bot.reply_to(message, f"⚠️ API Error: {str(e)}")
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid response from API. URL check karo.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Unexpected error: {str(e)}")

def send_main_message(chat_id):
    links = user_data.get(chat_id)
    if not links:
        return

    markup = InlineKeyboardMarkup()
    if links.get("song"):
        markup.add(InlineKeyboardButton("🎵 Get Song", callback_data="get_song"))
    if links.get("video"):
        markup.add(InlineKeyboardButton("🎬 Get Video", callback_data="get_video"))

    caption_text = f"🎬 *{links['title']}*\n\nKya download karna hai, choose karo 👇"

    if links.get("thumbnail"):
        bot.send_photo(
            chat_id,
            links["thumbnail"],
            caption=caption_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            chat_id,
            caption_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: CallbackQuery):
    chat_id = call.message.chat.id
    links = user_data.get(chat_id)
    if not links:
        bot.answer_callback_query(call.id, "❌ Data nahi mila. Naya URL bhejo.")
        return

    if call.data == "get_song":
        if links.get("song"):
            bot.answer_callback_query(call.id, "🎵 Song upload ho raha hai...")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back", callback_data="go_back"))
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            bot.send_audio(chat_id, links["song"], caption=f"🎵 *{links['title']}*", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ Song nahi hai.")

    elif call.data == "get_video":
        if links.get("video"):
            bot.answer_callback_query(call.id, "🎬 Video upload ho raha hai...")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back", callback_data="go_back"))
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            bot.send_video(chat_id, links["video"], caption=f"🎬 *{links['title']}*", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ Video nahi hai.")

    elif call.data == "go_back":
        bot.answer_callback_query(call.id, "⬅️ Wapas ja rahe hain...")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        send_main_message(chat_id)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def home():
    return 'Telegram Bot chal raha hai!'

def set_webhook():
    public_url = os.environ.get('PUBLIC_URL') or os.environ.get('RENDER_EXTERNAL_URL') or 'https://<your-app-name>.koyeb.app'
    webhook_url = f"{public_url}/webhook"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"Webhook set ho gaya: {webhook_url}")

if __name__ == '__main__':
    set_webhook()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
