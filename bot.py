import telebot
from telebot import types
import requests
import re
import threading
from datetime import datetime
from flask import Flask
import os

app = Flask(__name__)

# === CONFIG ===
BOT_TOKEN = "8575320394:AAHTTuOEEEJ1bN2XBSidHpTFer_785X5e6A"
CHANNEL_USERNAME = "@DarkWeb_MarketStore"
CHANNEL_ID = "@DarkWeb_MarketStore"
SUPPORT_USERNAME = "Backdoor_Operator"

BTC_WALLET = "bc1qydlfhxwkv50zcxzc5z5evuadhfh7dsexg9wqtt"
ZEC_WALLET = "t1P3JNGK4q8RdTL9NTav6J5kzGcWitPXX7k"

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# Cache & storage
product_names = {}
price_cache = {"bitcoin": {"price": 0, "time": 0}, "zcash": {"price": 0, "time": 0}}

def get_live_price(crypto="bitcoin"):
    now = datetime.now().timestamp()
    cache = price_cache[crypto]
    if cache["price"] > 0 and now - cache["time"] < 60:
        return cache["price"]
    try:
        price = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd",
            timeout=8
        ).json()[crypto]["usd"]
        price_cache[crypto] = {"price": price, "time": now}
        return price
    except:
        return 103000 if crypto == "bitcoin" else 185

def parse_product(text):
    if not text or "#DH" not in text:
        return None
    item_id = re.search(r'#DH\d+', text).group()
    price_match = re.search(r'(\d+)\s*USD', text, re.IGNORECASE)
    if not price_match:
        return None
    price = int(price_match.group(1))
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    name = lines[1] if len(lines) > 1 else "Item"
    status = "SOLD" if re.search(r'status:\s*sold', text, re.IGNORECASE) else "AVAILABLE"
    return {"item_id": item_id, "name": name, "price": price, "status": status}

def is_member(user_id):
    try:
        return bot.get_chat_member(CHANNEL_ID, user_id).status in ["member", "administrator", "creator"]
    except:
        return False

def get_time():
    return datetime.now().strftime("%b %d, %Y – %I:%M %p EAT")

def get_user_display(user):
    """Returns @username or FirstName – perfect for scary personal touch"""
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Stranger"

# === /start – NOW PERSONALIZED ===
@bot.message_handler(commands=['start'])
def start(msg):
    user_tag = get_user_display(msg.from_user)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("I Joined", callback_data="check_join"))
    bot.send_message(msg.chat.id,
        f"<b>DARKWEB PRODUCTS</b>\n"
        f"Hello <b>{user_tag}</b> 👁\n"
        "Worldwide underground prices | Fast delivery\n"
        "We already know who you are.\n\n"
        f"Join our channel to continue:\n{CHANNEL_USERNAME}\n\n"
        f"Time: {get_time()}",
        parse_mode="HTML", reply_markup=markup)

# === Check Join – PERSONALIZED ===
@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def check_join(call):
    user_tag = get_user_display(call.from_user)
    if is_member(call.from_user.id):
        bot.edit_message_text(
            f"<b>{user_tag}</b> – Access granted.\n"
            "Forward any product post from our channel to order.\n"
            "We are watching.",
            call.message.chat.id, call.message.message_id, parse_mode="HTML"
        )
        bot.answer_callback_query(call.id, "Welcome to the dark side.")
    else:
        bot.answer_callback_query(call.id, f"{user_tag} – Join the channel first!", show_alert=True)

# === FORWARD PRODUCT ===
@bot.message_handler(content_types=['photo', 'text'])
def handle_forward(message):
    if not message.forward_from_chat or message.forward_from_chat.username != CHANNEL_USERNAME[1:]:
        return
    if not is_member(message.from_user.id):
        bot.reply_to(message, "Join the channel first.")
        return

    text = (message.caption or message.text or "")
    info = parse_product(text)
    if not info:
        bot.reply_to(message, "Invalid product format.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(message, f"{info['item_id']} – SOLD OUT")
        return

    user_tag = get_user_display(message.from_user)
    product_names[message.chat.id] = info

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Bitcoin", callback_data=f"pay_BTC_{info['item_id']}_{info['price']}"),
        types.InlineKeyboardButton("Zcash",   callback_data=f"pay_ZEC_{info['item_id']}_{info['price']}")
    )
    bot.send_message(message.chat.id,
        f"<b>{info['item_id']} Verified – {user_tag}</b>\n"
        f"{info['name']}\n\n"
        f"<b>${info['price']:,} USD</b>\n"
        f"Worldwide delivery: 8–12 days\n\n"
        f"Time: {get_time()}\n\n"
        "Choose payment method:",
        parse_mode="HTML", reply_markup=markup)

# === PAYMENT – FULL SCARY PERSONALIZATION ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def show_payment(call):
    try:
        _, crypto, item_id, price_str = call.data.split("_", 3)
        price = int(price_str)
    except:
        bot.answer_callback_query(call.id, "Error. Try again.", show_alert=True)
        return

    info = product_names.get(call.from_user.id, {"name": "Item", "item_id": item_id})
    user_tag = get_user_display(call.from_user)

    if crypto == "BTC":
        wallet = BTC_WALLET
        amount = round(price / get_live_price("bitcoin"), 8)
        coin = "BTC"
    else:
        wallet = ZEC_WALLET
        amount = round(price / get_live_price("zcash"), 6)
        coin = "ZEC"

    # SCARY SUPPORT MESSAGE WITH USER'S NAME
    support_text = (
        f"NEW PAYMENT DETECTED\n\n"
        f"Buyer: {user_tag}\n"
        f"User ID: {call.from_user.id}\n"
        f"Product: {info['name']}\n"
        f"Item ID: {info['item_id']}\n"
        f"Price: ${price:,} USD\n"
        f"Crypto: {coin} – {amount}\n\n"
        f"Payment window closing soon.\n"
        f"Confirm or we vanish forever."
    )
    support_url = f"https://t.me/{SUPPORT_USERNAME}?text={requests.utils.quote(support_text)}"

    text = (
        f"<b>{item_id} – {user_tag}</b>\n"
        f"{info['name']}\n\n"
        f"<b>${price:,} USD</b>\n"
        f"≈ <code>{amount}</code> {coin} (live)\n\n"
        f"<b>Send to this address NOW:</b>\n"
        f"<code>{wallet}</code>\n\n"
        f"Worldwide · 8–12 days\n"
        f"Time: {get_time()}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Copy Wallet Address", callback_data=f"copy_{wallet}"))
    markup.add(types.InlineKeyboardButton("I Paid – Contact Support", url=support_url))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          parse_mode="HTML", reply_markup=markup)
    product_names.pop(call.from_user.id, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy_wallet(call):
    wallet = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, wallet, show_alert=True)

@app.route('/')
def home():
    return "DarkWeb Bot Running | Personalized | Railway 2025"

# === RAILWAY START ===
if __name__ == "__main__":
    print("DarkWeb Bot Starting – Personalized Mode Activated...")
    threading.Thread(target=bot.infinity_polling, kwargs={"none_stop": True}, daemon=True).start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
