import telebot
from telebot import types
import requests
import re
import threading
from datetime import datetime
from flask import Flask

app = Flask(__name__)

# === CONFIG ===
BOT_TOKEN = "8575320394:AAEKlwpqbny9H2MEz8tXMSNStmvHRG9KMOM"
CHANNEL_USERNAME = "@DarkWeb_MarketStore"
CHANNEL_ID = "@DarkWeb_MarketStore"  # Can be username or ID
SUPPORT_USERNAME = "Backdoor_Operator"
BTC_WALLET = "bc1qydlfhxwkv50zcxzc5z5evuadhfh7dsexg9wqtt"
ZEC_WALLET = "t1P3JNGK4q8RdTL9NTav6J5kzGcWitPXX7k"

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# Temporary storage
product_names = {}

# === PRICE FETCH WITH CACHE ===
price_cache = {"bitcoin": {"price": 0, "time": 0}, "zcash": {"price": 0, "time": 0}}

def get_live_price(crypto="bitcoin"):
    now = datetime.now().timestamp()
    cache = price_cache[crypto]
    if now - cache["time"] < 60:  # Cache for 60 seconds
        return cache["price"] if cache["price"] > 0 else 103000 if crypto == "bitcoin" else 185

    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd"
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        price = resp.json()[crypto]["usd"]
        price_cache[crypto] = {"price": price, "time": now}
        return price
    except Exception as e:
        print(f"Price fetch failed ({crypto}): {e}")
        return 103000 if crypto == "bitcoin" else 185

# === HELPER FUNCTIONS ===
def parse_product(text):
    if not text or "#DH" not in text:
        return None
    item_id_match = re.search(r'#DH\d+', text)
    if not item_id_match:
        return None
    item_id = item_id_match.group()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    name = lines[1] if len(lines) > 1 else "Unknown Item"
    price_match = re.search(r'\$([0-9,]+)', text)
    if not price_match:
        return None
    price = int(price_match.group(1).replace(",", ""))
    status = "SOLD" if any("sold" in l.lower() for l in lines) else "AVAILABLE"
    return {"item_id": item_id, "name": name, "price": price, "status": status}

def is_member(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def get_time():
    return datetime.now().strftime("%b %d, %Y – %I:%M %p EAT")

# === HANDLERS ===
@bot.message_handler(commands=['start'])
def start(msg):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("I Joined", callback_data="check_join"))
    bot.send_message(msg.chat.id,
        "<b>DARKWEB PRODUCTS</b>\n"
        "Worldwide underground prices | Fast delivery\n"
        "We source globally — you pay less | BTC · ZEC\n\n"
        f"Join the channel first:\n{CHANNEL_USERNAME}\n\n"
        f"Time: {get_time()}",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def check_join(call):
    if is_member(call.from_user.id):
        bot.edit_message_text("Access granted.\nForward any product post to order.",
                              call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Welcome!")
    else:
        bot.answer_callback_query(call.id, "Join the channel first.", show_alert=True)

@bot.message_handler(content_types=['photo', 'text'])
def handle_forward(message):
    if not message.forward_from_chat:
        return
    if message.forward_from_chat.username != CHANNEL_USERNAME[1:]:
        return
    if not is_member(message.from_user.id):
        bot.reply_to(message, "Join the channel first.")
        return

    text = message.caption if hasattr(message, 'caption') and message.caption else message.text
    if not text:
        return

    info = parse_product(text)
    if not info:
        bot.reply_to(message, "Invalid product format.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(message, f"{info['item_id']} – SOLD")
        return

    # Save product name for this user
    product_names[message.chat.id] = info["name"]

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Bitcoin", callback_data=f"pay_BTC_{info['item_id']}_{info['price']}"),
        types.InlineKeyboardButton("Zcash", callback_data=f"pay_ZEC_{info['item_id']}_{info['price']}")
    )

    bot.send_message(message.chat.id,
        f"<b>{info['item_id']} Verified</b>\n"
        f"{info['name']}\n\n"
        f"<b>${info['price']:,} USD</b>\n"
        f"Worldwide delivery: 8–12 days\n\n"
        f"Time: {get_time()}\n\n"
        "Choose payment method:",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def show_payment(call):
    try:
        parts = call.data.split("_")
        if len(parts) != 4:
            raise ValueError("Invalid callback format")
        crypto = parts[1]      # BTC or ZEC
        item_id = parts[2]     # #DH4471
        price = int(parts[3])  # 720
    except Exception as e:
        print(f"Callback parse error: {e} | data: {call.data}")
        bot.answer_callback_query(call.id, "Error. Try again.", show_alert=True)
        return

    product_name = product_names.get(call.from_user.id, "Item")

    if crypto == "BTC":
        wallet = BTC_WALLET
        amount = round(price / get_live_price("bitcoin"), 8)
        coin = "BTC"
    else:
        wallet = ZEC_WALLET
        amount = round(price / get_live_price("zcash"), 6)
        coin = "ZEC"

    text = (
        f"<b>{item_id} Verified</b>\n"
        f"{product_name}\n\n"
        f"<b>${price:,} USD</b>\n"
        f"≈ <code>{amount}</code> {coin} (live rate)\n\n"
        f"<b>Send exactly this amount to:</b>\n"
        f"<code>{wallet}</code>\n\n"
        f"Worldwide · 8–12 days delivery\n"
        f"Time: {get_time()}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Copy Wallet Address", callback_data=f"copy_{wallet}"))
    markup.add(types.InlineKeyboardButton("I Paid – Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}"))

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              parse_mode="HTML", reply_markup=markup)
        # Clear saved name after use
        product_names.pop(call.from_user.id, None)
    except Exception as e:
        print(f"Edit message failed: {e}")
        bot.answer_callback_query(call.id, "Error. Try again.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy_wallet(call):
    wallet = call.data[5:]
    bot.answer_callback_query(call.id, wallet, show_alert=True)

# === FLASK KEEP-ALIVE ===
@app.route('/')
def home():
    return "DarkWeb Products Bot – Running Smoothly"

# === RUN BOT + WEB SERVER ===
if __name__ == "__main__":
    print("Bot started...")
    threading.Thread(target=bot.infinity_polling, kwargs={"none_stop": True}, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
