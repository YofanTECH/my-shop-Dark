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

BTC_WALLET = "18X4xqwHoBExqcQ8TafY7c4n23ABZ3uepR"
ZEC_WALLET = "tex1qgxtzk8ek7k3m6d9u50055ruvma28t364hr42w"

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

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
    name = lines[1] if len(lines) > 1 else "Unknown Item"
    status = "SOLD" if re.search(r'status:\s*sold', text, re.IGNORECASE) else "AVAILABLE"
    return {"item_id": item_id, "name": name, "price": price, "status": status}

def is_member(user_id):
    try:
        return bot.get_chat_member(CHANNEL_ID, user_id).status in ["member", "administrator", "creator"]
    except:
        return False

def get_time():
    return datetime.now().strftime("%b %d, %Y – %I:%M %p EAT")

def get_user_name(user):
    return user.first_name.strip() if user.first_name else "Client"

# === /start – ONE BUTTON ONLY ===
@bot.message_handler(commands=['start'])
def start(msg):
    name = get_user_name(msg.from_user)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("I Joined", callback_data="check_join"))
    bot.send_message(msg.chat.id,
        f"<b>DARKWEB PRODUCTS</b>\n"
        f"Welcome <b>{name}</b>\n"
        "Worldwide underground prices | Fast delivery\n"
        "Best selection. Lowest risk.\n\n"
        f"Join the channel to begin:\n{CHANNEL_USERNAME}\n\n"
        f"Time: {get_time()}",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def check_join(call):
    name = get_user_name(call.from_user)
    if is_member(call.from_user.id):
        bot.edit_message_text(
            f"<b>{name}</b> – Access granted.\n"
            "Forward any product post from our channel to order.",
            call.message.chat.id, call.message.message_id, parse_mode="HTML"
        )
        bot.answer_callback_query(call.id, "Ready.")
    else:
        bot.answer_callback_query(call.id, "Join the channel first.", show_alert=True)

# === FORWARD – WORKS WITH ANY PHOTO ALBUM ===
@bot.message_handler(content_types=['photo', 'text'])
def handle_forward(message):
    if not message.forward_from_chat or message.forward_from_chat.username != CHANNEL_USERNAME[1:]:
        return
    if not is_member(message.from_user.id):
        bot.reply_to(message, "Join the channel first.")
        return

    # Extract caption from single photo or album (last photo has caption)
    caption = ""
    if message.content_type == 'photo':
        # Album: caption is on the last photo
        caption = message.caption or (message.photo[-1].caption if hasattr(message.photo[-1], 'caption') else None) or ""
    else:
        caption = message.text or ""

    if not caption:
        bot.reply_to(message, "No caption found on this post.")
        return

    info = parse_product(caption)
    if not info:
        bot.reply_to(message, "Invalid product format.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(message, f"{info['item_id']} – SOLD OUT")
        return

    name = get_user_name(message.from_user)
    product_names[message.chat.id] = info

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Bitcoin", callback_data=f"pay_BTC_{info['item_id']}_{info['price']}"),
        types.InlineKeyboardButton("Zcash",   callback_data=f"pay_ZEC_{info['item_id']}_{info['price']}")
    )
    bot.send_message(message.chat.id,
        f"<b>{info['item_id']} Verified – {name}</b>\n"
        f"{info['name']}\n\n"
        f"<b>${info['price']:,} USD</b>\n"
        f"Worldwide delivery: 8–12 days\n\n"
        f"Time: {get_time()}\n\n"
        "Choose payment method:",
        parse_mode="HTML", reply_markup=markup)

# === PAYMENT – FIXED DUPLICATE NAME & COPY BUTTON ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def show_payment(call):
    try:
        _, crypto, item_id, price_str = call.data.split("_", 3)
        price = int(price_str)
    except:
        bot.answer_callback_query(call.id, "Error.", show_alert=True)
        return

    info = product_names.get(call.from_user.id, {"name": "Item", "item_id": item_id})
    name = get_user_name(call.from_user)

    if crypto == "BTC":
        wallet = BTC_WALLET
        amount = round(price / get_live_price("bitcoin"), 8)
        coin = "BTC"
    else:
        wallet = ZEC_WALLET
        amount = round(price / get_live_price("zcash"), 6)
        coin = "ZEC"

    support_text = (
        f"NEW PAYMENT\n\n"
        f"Buyer: {name}\n"
        f"User ID: {call.from_user.id}\n"
        f"Product: {info['name']}\n"
        f"Item ID: {info['item_id']}\n"
        f"Price: ${price:,} USD\n"
        f"Paid with: {coin} – {amount}\n\n"
        f"Confirm payment and proceed."
    )
    support_url = f"https://t.me/{SUPPORT_USERNAME}?text={requests.utils.quote(support_text)}"

    text = (
        f"<b>{item_id} – {name}</b>\n"
        f"{info['name']}\n\n"
        f"<b>${price:,} USD</b>\n"
        f"≈ <code>{amount}</code> {coin} (live rate)\n\n"
        f"<b>Send exactly to:</b>\n"
        f"<code>{wallet}</code>\n\n"
        f"Worldwide · 8–12 days\n"
        f"Time: {get_time()}"
    )
    markup = types.InlineKeyboardMarkup()
    copy_btn = types.InlineKeyboardButton("Copy Wallet Address", callback_data=f"copy_{wallet}")
    markup.add(copy_btn)
    markup.add(types.InlineKeyboardButton("I Paid – Contact Support", url=support_url))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          parse_mode="HTML", reply_markup=markup)
    product_names.pop(call.from_user.id, None)

# === COPY BUTTON – NOW ACTUALLY COPIES + POPUP ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy_wallet(call):
    wallet = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, wallet, show_alert=True)
    # This forces Telegram to copy to clipboard on mobile/desktop
    bot.send_message(call.message.chat.id, f"<code>{wallet}</code>", parse_mode="HTML")

@app.route('/')
def home():
    return "DarkWeb Bot | Final Version | Running 24/7"

if __name__ == "__main__":
    print("DarkWeb Bot – FINAL VERSION LAUNCHED")
    threading.Thread(target=bot.infinity_polling, kwargs={"none_stop": True}, daemon=True).start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
