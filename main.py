import re
import telebot
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask, request
import os

# Replace with your actual Telegram bot token
BOT_TOKEN = 'YOUR_ACTUAL_BOT_TOKEN'  # Apna real bot token yahan daal do (@BotFather se milega)
API_BASE_URL = 'https://socialdownloder2.anshapi.workers.dev/?url='

# Initialize Flask app and Telegram bot
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# Social media URL patterns
SOCIAL_MEDIA_PATTERNS = re.compile(
    r"(https?:\/\/(?:www\.)?(?:youtube\.com|youtu\.be|instagram\.com|facebook\.com|fb\.watch|twitter\.com|x\.com|tiktok\.com|threads\.net|pinterest\.com|reddit\.com)[^\s]*)",
    re.IGNORECASE
)

# Store data temporarily for each user
user_data = {}

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "Hey! 👋 Send me any social media video URL (YouTube, Instagram, etc.) and I’ll fetch download links for you! 📥")

@bot.message_handler(func=lambda message: True)
def handle_url(message):
    url_match = SOCIAL_MEDIA_PATTERNS.search(message.text.strip())
    if not url_match:
        return  # Ignore non-URL messages

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
            bot.reply_to(message, "❌ No download links found! Please check the URL.")
            return

        # Separate song & video links
        song_link = None
        video_link = None
        for media in medias:
            if 'audio' in media.get('type', '').lower():
                song_link = media.get('url')
            elif 'video' in media.get('type', '').lower():
                video_link = media.get('url')

        if not song_link and not video_link:
            bot.reply_to(message, "❌ No valid media found!")
            return

        # Save links + original message data
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
        bot.reply_to(message, "⚠️ Invalid response from API. Please check the URL.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Unexpected error: {str(e)}")

def send_main_message(chat_id):
    """Send the main thumbnail + buttons view"""
    links = user_data.get(chat_id)
    if not links:
        return

    markup = InlineKeyboardMarkup()
    if links.get("song"):
        markup.add(InlineKeyboardButton("🎵 Get Song", callback_data="get_song"))
    if links.get("video"):
        markup.add(InlineKeyboardButton("🎬 Get Video", callback_data="get_video"))

    caption_text = f"🎬 *{links['title']}*\n\nChoose what you want to download 👇"

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
        bot.answer_callback_query(call.id, "❌ Data not found. Send a new URL.")
        return

    if call.data == "get_song":
        if links.get("song"):
            bot.answer_callback_query(call.id, "🎵 Uploading Song...")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back", callback_data="go_back"))
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            bot.send_audio(chat_id, links["song"], caption=f"🎵 *{links['title']}*", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ No song available.")

    elif call.data == "get_video":
        if links.get("video"):
            bot.answer_callback_query(call.id, "🎬 Uploading Video...")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back", callback_data="go_back"))
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            bot.send_video(chat_id, links["video"], caption=f"🎬 *{links['title']}*", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ No video available.")

    elif call.data == "go_back":
        bot.answer_callback_query(call.id, "⬅️ Going back...")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        send_main_message(chat_id)

# Flask route to handle Telegram webhook updates
@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK', 200

# Root route for health check
@app.route('/')
def home():
    return 'Telegram Bot is running!'

# Automatically set webhook on startup
def set_webhook():
    # Get public URL from environment variables
    public_url = os.environ.get('PUBLIC_URL') or os.environ.get('RENDER_EXTERNAL_URL') or 'https://<your-app-name>.onrender.com'  # Replace fallback with your app URL
    webhook_url = f"{public_url}/webhook"
    
    # Remove existing webhook and set new one
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"Webhook set to: {webhook_url}")

if __name__ == '__main__':
    # Set webhook before starting Flask app
    set_webhook()
    # Run Flask on the port provided by Koyeb/Render (default 8080)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
