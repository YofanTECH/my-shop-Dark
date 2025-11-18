import telebot
from telebot import types
import requests
import re
import threading
from flask import Flask
import time

app = Flask(__name__)

BOT_TOKEN        = "8575320394:AAEKlwpqbny9H2MEz8tXMSNStmvHRG9KMOM"
CHANNEL_USERNAME = "@DarkWeb_MarketStore"
CHANNEL_ID       = "@DarkWeb_MarketStore"
SUPPORT_USERNAME = "Backdoor_Operator"

BTC_WALLET = "bc1qydlfhxwkv50zcxzc5z5evuadhfh7dsexg9wqtt"
ZEC_WALLET = "t1gZ4X8wZ9v5Kj9fK9fK9fK9fK9fK9fK9fK"

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()
time.sleep(2)

def get_live_price(crypto="bitcoin"):
    try:
        return requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd", timeout=6).json()[crypto]["usd"]
    except:
        return 101500 if crypto == "bitcoin" else 210

def parse_product(text):
    if not text or "#DH" not in text: return None

    # Extract #DHxxxx
    item_id = re.search(r'#DH\d+', text)
    if not item_id: return None
    item_id = item_id.group()

    # Extract name (line after #DH)
    name_match = re.search(r'#DH\d+\s*\n\s*(.+?)(?:\n|$)', text, re.DOTALL)
    name = name_match.group(1).strip() if name_match else "Item"

    # Extract price
    price_match = re.search(r'\$([0-9,]+)', text)
    if not price_match: return None
    price = int(price_match.group(1).replace(",", ""))

    # Check if sold
    status = "SOLD" if re.search(r'status\s*:\s*sold', text, re.I) else "AVAILABLE"

    return {"item_id": item_id, "name": name, "price": price, "status": status}

def is_member(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ["member", "administrator", "creator"]
    except:
        return False

@bot.message_handler(commands=['start'])
def start(msg):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("I Joined", callback_data="check_join"))
    bot.send_message(msg.chat.id,
        "<b>DARKWEB PRODUCTS</b>\n"
        "Worldwide underground prices | Fast delivery\n"
        "We source globally — you pay less | BTC · ZEC\n\n"
        f"Join the channel first:\n{CHANNEL_USERNAME}",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def check_join(call):
    if is_member(call.from_user.id):
        bot.edit_message_text("Access granted.\nForward any product post to order.",
                              call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Join the channel first.", show_alert=True)

# NOW WORKS WITH PHOTO + CAPTION 100%
@bot.message_handler(content_types=['photo', 'text'])
def handle_forward(message):
    if not message.forward_from_chat or f"@{message.forward_from_chat.username}" != CHANNEL_USERNAME:
        return
    if not is_member(message.from_user.id):
        bot.reply_to(message, "Join the channel first.")
        return

    text = message.caption if hasattr(message, 'caption') and message.caption else message.text
    if not text: return

    info = parse_product(text)
    if not info:
        bot.reply_to(message, "Invalid product format.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(message, f"{info['item_id']} – SOLD")
        return

    # Clean message + REAL inline buttons (under the message)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Bitcoin", callback_data=f"pay_BTC_{info['item_id']}_{info['price']}"))
    markup.add(types.InlineKeyboardButton("Zcash",   callback_data=f"pay_ZEC_{info['item_id']}_{info['price']}"))

    bot.send_message(
        message.chat.id,
        f"<b>{info['item_id']}</b>\n"
        f"{info['name']}\n\n"
        f"<b>${info['price']} USD</b>\n"
        f"Worldwide delivery: 8–12 days\n\n"
        f"Choose payment method:",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def show_payment(call):
    crypto, item_id, price = call.data.split("_")[1:]
    price = int(price)

    if crypto == "BTC":
        wallet = BTC_WALLET
        rate = get_live_price("bitcoin")
        amount = round(price / rate, 8)
        coin = "BTC"
    else:
        wallet = ZEC_WALLET
        rate = get_live_price("zcash")
        amount = round(price / rate, 6)
        coin = "ZEC"

    text = f"<b>{item_id}</b>\n" \
           f"{call.message.html_text.split('</b>')[1].split('<b>')[0].strip()}\n\n" \
           f"<b>${price} USD</b>\n" \
           f"≈ <code>{amount}</code> {coin} (live rate)\n\n" \
           f"<code>{wallet}</code>\n\n" \
           f"Worldwide · 8–12 days"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Copy Address", callback_data=f"copy_{wallet}"))
    markup.add(types.InlineKeyboardButton("I Paid", url=f"https://t.me/{SUPPORT_USERNAME}?text=Payment%20sent%20–%20{item_id}%20–%20%24{price}%20via%20{crypto}"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy(c):
    bot.answer_callback_query(c.id, c.data[5:], show_alert=True)

@app.route('/')
def home(): return "Bot running"

if __name__ == "__main__":
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
