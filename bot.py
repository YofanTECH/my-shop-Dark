import telebot
from telebot import types
import requests
import re
import threading
from flask import Flask

app = Flask(__name__)

# ====== CHANGE ONLY THESE 3 LINES ======
BOT_TOKEN = "8575320394:AAEKlwpqbny9H2MEz8tXMSNStmvHRG9KMOM"          # From @BotFather
CHANNEL_USERNAME = "@DarkWeb_MarketStore"               # Your channel with @
SUPPORT_USERNAME = "@Backdoor_Operator"            # Without @
# =======================================

bot = telebot.TeleBot(BOT_TOKEN)

def get_btc_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        return r.json()["bitcoin"]["usd"]
    except:
        return 96000

def parse_product(text):
    if not text or "#DH" not in text:
        return None
    lines = text.strip().split("\n")
    item_id = lines[0].split()[0]
    name = lines[1].strip() if len(lines) > 1 else "Unknown Item"
    price_match = re.search(r'\$([0-9,]+)', text)
    price = int(price_match.group(1).replace(",", "")) if price_match else None
    if price is None:
        return None
    if any(x in text.lower() for x in ["sold", "taken", "reserved"]):
        return {**locals(), "status": "SOLD"}
    return {"item_id": item_id, "name": name, "price": price, "status": "AVAILABLE"}

main_menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add("Browse Products", "Service & Delivery")
main_menu.add("How to Order", "Live Support")

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Drop active.\nForward any #DHxxxx post to order.", reply_markup=main_menu)

@bot.message_handler(func=lambda m: m.text == "Browse Products")
def browse(m):
    bot.send_message(m.chat.id, "Forward product post from channel.\nOnly #DHxxxx accepted.")

@bot.message_handler(func=lambda m: m.text == "Service & Delivery")
def service(m):
    bot.send_message(m.chat.id, "Ethiopia → 3–7 days\nWorldwide → 8–12 days\nBTC only • No logs")

@bot.message_handler(func=lambda m: m.text == "How to Order")
def howto(m):
    bot.send_message(m.chat.id, "1. Forward post\n2. Send exact $ in BTC\n3. We confirm instantly")

@bot.message_handler(func=lambda m: m.text == "Live Support")
def support(m):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Open Support", url=f"https://t.me/{SUPPORT_USERNAME}"))
    bot.send_message(m.chat.id, "Tap to contact support:", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(m):
    if not m.forward_from_chat:
        return
    if f"@{m.forward_from_chat.username}" != CHANNEL_USERNAME:
        bot.reply_to(m, "Wrong channel.")
        return

    info = parse_product(m.text or m.caption)
    if not info:
        bot.reply_to(m, "Invalid post format.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(m, f"{info['item_id']} – SOLD\nCheck new drops.")
        return

    btc_price = get_btc_price()
    btc_amount = round(info["price"] / btc_price, 8)
    wallet = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"  # Change per order

    text = f"""
{info['item_id']} – Bitcoin Payment

Send exactly ${info['price']}.00 USD
≈ {btc_amount} BTC (live)

Wallet:
<code>{wallet}</code>

25:00 minutes left
We detect payment instantly.
    """.strip()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Copy BTC Amount", callback_data=f"copy_{btc_amount}"))
    markup.add(types.InlineKeyboardButton("Copy Address", callback_data=f"copy_{wallet}"))
    markup.add(types.InlineKeyboardButton("Support", url=f"https://t.me/{SUPPORT_USERNAME}?text=Order%20{info['item_id']}"))

    bot.send_message(m.chat.id, text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy(c):
    bot.answer_callback_query(c.id, c.data[5:], show_alert=True)

# Start bot polling in background thread
def start_bot():
    print("Bot starting...")
    bot.infinity_polling()

if __name__ == '__main__':
    # Start bot in thread
    threading.Thread(target=start_bot, daemon=True).start()
    
    # Minimal Flask to keep service alive (Koyeb requires it)
    @app.route('/')
    def health():
        return "Bot running"
    
    app.run(host='0.0.0.0', port=8000)
