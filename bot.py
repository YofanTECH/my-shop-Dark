import telebot
from telebot import types
import requests
import re
import threading
from datetime import datetime, timedelta
from flask import Flask

app = Flask(__name__)

BOT_TOKEN        = "8575320394:AAEKlwpqbny9H2MEz8tXMSNStmvHRG9KMOM"
CHANNEL_USERNAME = "@DarkWeb_MarketStore"
CHANNEL_ID       = "@DarkWeb_MarketStore"
SUPPORT_USERNAME = "Backdoor_Operator"

BTC_WALLET = "bc1qydlfhxwkv50zcxzc5z5evuadhfh7dsexg9wqtt"
ZEC_WALLET = "t1P3JNGK4q8RdTL9NTav6J5kzGcWitPXX7k"

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# Store: {message_id: {"expiry": time, "chat_id": id, "base_text": text}}
active_orders = {}

def get_live_price(crypto="bitcoin"):
    try:
        return requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd", timeout=6).json()[crypto]["usd"]
    except:
        return 101500 if crypto == "bitcoin" else 210

def parse_product(text):
    if not text or "#DH" not in text: return None
    item_id = re.search(r'#DH\d+', text).group()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    name = lines[1] if len(lines) > 1 else "Unknown Item"
    price_match = re.search(r'\$([0-9,]+)', text)
    if not price_match: return None
    price = int(price_match.group(1).replace(",", ""))
    status = "SOLD" if any("sold" in l.lower() for l in lines) else "AVAILABLE"
    return {"item_id": item_id, "name": name, "price": price, "status": status}

def is_member(user_id):
    try:
        return bot.get_chat_member(CHANNEL_ID, user_id).status in ["member", "administrator", "creator"]
    except:
        return False

def get_time():
    return datetime.now().strftime("%b %d, %Y – %I:%M %p EAT")

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
    else:
        bot.answer_callback_query(call.id, "Join the channel first.", show_alert=True)

@bot.message_handler(content_types=['photo', 'text'])
def handle_forward(message):
    if not message.forward_from_chat or message.forward_from_chat.username != CHANNEL_USERNAME[1:]:
        return
    if not is_member(message.from_user.id):
        bot.reply_to(message, "Join the channel first.")
        return

    text = message.caption if message.caption else message.text
    info = parse_product(text)
    if not info:
        bot.reply_to(message, "Invalid product format.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(message, f"{info['item_id']} – SOLD")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Bitcoin", callback_data=f"pay_BTC_{info['item_id']}_{info['price']}"))
    markup.add(types.InlineKeyboardButton("Zcash",   callback_data=f"pay_ZEC_{info['item_id']}_{info['price']}"))

    bot.send_message(message.chat.id,
        f"<b>{info['item_id']} Verified</b>\n"
        f"{info['name']}\n\n"
        f"<b>${info['price']} USD</b>\n"
        f"Worldwide delivery: 8–12 days\n\n"
        f"Time: {get_time()}\n\n"
        f"Choose payment method:",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def show_payment(call):
    crypto, item_id, price_str = call.data.split("_", 2)[1:]
    price = int(price_str.split("_")[0])
    expiry = datetime.now() + timedelta(minutes=20)

    if crypto == "BTC":
        wallet = BTC_WALLET
        amount = round(price / get_live_price("bitcoin"), 8)
        coin = "BTC"
    else:
        wallet = ZEC_WALLET
        amount = round(price / get_live_price("zcash"), 6)
        coin = "ZEC"

    base_text = f"<b>{item_id} Verified</b>\n" \
                f"{call.message.html_text.split('</b>')[1].split('<b>')[0].split('Worldwide')[0].strip()}\n\n" \
                f"<b>${price} USD</b>\n" \
                f"≈ <code>{amount}</code> {coin}\n\n" \
                f"<code>{wallet}</code>\n\n" \
                f"Expires in: {{}}\n" \
                f"Worldwide · 8–12 days\n" \
                f"Time: {get_time()}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Copy Address", callback_data=f"copy_{wallet}"))
    markup.add(types.InlineKeyboardButton("I Paid", url=f"https://t.me/{SUPPORT_USERNAME}"))

    bot.edit_message_text(base_text.format("20:00"), call.message.chat.id, call.message.message_id,
                          parse_mode="HTML", reply_markup=markup)

    # Save order
    msg_id = call.message.message_id
    active_orders[msg_id] = {
        "expiry": expiry,
        "chat_id": call.message.chat.id,
        "base_text": base_text,
        "markup": markup
    }

    # Live countdown
    def countdown():
        while msg_id in active_orders:
            remaining = int((active_orders[msg_id]["expiry"] - datetime.now()).total_seconds())
            if remaining <= 0:
                bot.edit_message_text("<b>Payment window closed</b>\nAddress expired.", 
                                    active_orders[msg_id]["chat_id"], msg_id, parse_mode="HTML")
                active_orders.pop(msg_id, None)
                break
            mins, secs = divmod(remaining, 60)
            try:
                bot.edit_message_text(
                    active_orders[msg_id]["base_text"].format(f"{mins:02d}:{secs:02d}"),
                    active_orders[msg_id]["chat_id"], msg_id,
                    parse_mode="HTML", reply_markup=active_orders[msg_id]["markup"]
                )
            except:
                pass
            time.sleep(10)

    threading.Thread(target=countdown, daemon=True).start()

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy(c):
    bot.answer_callback_query(c.id, c.data[5:], show_alert=True)

@app.route('/')
def home():
    return "DarkWeb Bot Running | Nov 18, 2025"

if __name__ == "__main__":
    threading.Thread(target=bot.infinity_polling, kwargs={"none_stop": True}, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
