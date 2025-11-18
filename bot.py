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
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd"
        return requests.get(url, timeout=6).json()[crypto]["usd"]
    except:
        return 101500 if crypto == "bitcoin" else 210

def parse_product(text):
    if not text or "#DH" not in text: return None
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2: return None

    item_id = re.search(r'#DH\d+', lines[0]).group()
    name = lines[1]

    price_match = re.search(r'\$([0-9,]+)', text)
    if not price_match: return None
    price = int(price_match.group(1).replace(",", ""))

    status_line = next((l for l in lines if l.lower().startswith("status:")), "Status: Available")
    status = "SOLD" if "sold" in status_line.lower() else "AVAILABLE"

    return {"item_id": item_id, "name": name, "price": price, "status": status}

def is_member(user_id):
    try:
        return bot.get_chat_member(CHANNEL_ID, user_id).status in ["member", "administrator", "creator"]
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

# Works with photo + caption AND text posts
@bot.message_handler(content_types=['text', 'photo', 'video'])
def handle_forward(message):
    if not message.forward_from_chat or f"@{message.forward_from_chat.username}" != CHANNEL_USERNAME:
        return
    if not is_member(message.from_user.id):
        bot.reply_to(message, "Join the channel first.")
        return

    # Get text from caption OR normal text
    text = message.caption if message.caption else message.text
    if not text: return

    info = parse_product(text)
    if not info:
        bot.reply_to(message, "Invalid format.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(message, f"{info['item_id']} – SOLD")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Bitcoin", callback_data=f"pay_BTC_{info['item_id']}_{info['price']}"))
    markup.add(types.InlineKeyboardButton("Zcash",   callback_data=f"pay_ZEC_{info['item_id']}_{info['price']}"))

    bot.send_message(message.chat.id,
 f"""{info['item_id']}
{info['name']}

${info['price']} USD
Worldwide delivery: 8–12 days

Select payment:""", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def show_payment(call):
    crypto, item_id, price = call.data.split("_")[1:]
    price = int(price)
    name = call.message.text.split("\n")[1]

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

    text = f"""
{item_id}
{name}

${price} USD
≈ {amount} {coin} (live)

<code>{wallet}</code>

Worldwide · 8–12 days
    """.strip()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Copy Address", callback_data=f"copy_{wallet}"))
    markup.add(types.InlineKeyboardButton("I Paid", url=f"https://t.me/{SUPPORT_USERNAME}?text=Payment%20sent%20–%20{item_id}%20–%20%24{price}%20via%20{crypto}"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy(c):
    bot.answer_callback_query(c.id, c.data[5:], show_alert=True)

@app.route('/')
def home(): return "Bot alive"

if __name__ == "__main__":
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
