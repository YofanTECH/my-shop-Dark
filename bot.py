import telebot
from telebot import types
import requests
import re
import threading
from flask import Flask
import time

app = Flask(__name__)

# YOUR DATA
BOT_TOKEN        = "8575320394:AAEKlwpqbny9H2MEz8tXMSNStmvHRG9KMOM"
CHANNEL_USERNAME = "@DarkWeb_MarketStore"
SUPPORT_USERNAME = "Backdoor_Operator"
BTC_WALLET       = "bc1qydlfhxwkv50zcxzc5z5evuadhfh7dsexg9wqtt"
ZEC_WALLET       = "t1gZ4X8wZ9v5Kj9fK9fK9fK9fK9fK9fK9fK"   # change later if needed

bot = telebot.TeleBot(BOT_TOKEN)

# THIS LINE FIXES YOUR 409 ERROR
bot.remove_webhook()
time.sleep(2)   # give Telegram time to process

# rest of your functions (unchanged)
def get_price(crypto="bitcoin"):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd"
        return requests.get(url, timeout=5).json()[crypto]["usd"]
    except:
        return 100000 if crypto == "bitcoin" else 200

def parse_product(text):
    if not text or "#DH" not in text: return None
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    item_id = lines[0].split()[0]
    name = " ".join(lines[1:2]) if len(lines)>1 else "Item"
    price_match = re.search(r'\$([0-9,]+)', text)
    if not price_match: return None
    price = int(price_match.group(1).replace(",",""))
    if any(w in text.lower() for w in ["sold","taken","reserved"]):
        return {"status":"SOLD","item_id":item_id}
    return {"item_id":item_id, "name":name, "price":price, "status":"AVAILABLE"}

@bot.message_handler(content_types=['text'])
def handle_forward(message):
    if not message.forward_from_chat or f"@{message.forward_from_chat.username}" != CHANNEL_USERNAME:
        return

    info = parse_product(message.text or message.caption)
    if not info:
        bot.reply_to(message, "Invalid post.")
        return
    if info["status"] == "SOLD":
        bot.reply_to(message, f"{info['item_id']} sold.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Bitcoin", callback_data=f"crypto_BTC_{info['item_id']}_{info['price']}"),
        types.InlineKeyboardButton("Zcash",   callback_data=f"crypto_ZEC_{info['item_id']}_{info['price']}")
    )
    bot.send_message(message.chat.id,
        f"{info['item_id']}\n{info['name']}\n\n${info['price']} USD\n\nChoose payment method:",
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("crypto_"))
def crypto_chosen(call):
    crypto, item_id, price = call.data.split("_")[1:]
    price = int(price)

    if crypto == "BTC":
        wallet = BTC_WALLET
        rate = get_price("bitcoin")
        amount = round(price / rate, 8)
        coin = "BTC"
    else:
        wallet = ZEC_WALLET
        rate = get_price("zcash")
        amount = round(price / rate, 6)
        coin = "ZEC"

    text = f"""
{item_id}
{call.message.text.split('\n')[1]}

${price} USD
≈ {amount} {coin}

<code>{wallet}</code>
    """.strip()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Copy Address", callback_data=f"copy_{wallet}"))
    support_url = f"https://t.me/{SUPPORT_USERNAME}?text=Payment%20done%20–%20{item_id}%20–%20{price}%20USD%20via%20{crypto}"
    markup.add(types.InlineKeyboardButton("I Paid", url=support_url))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("copy_"))
def copy_addr(c):
    bot.answer_callback_query(c.id, c.data[5:], show_alert=True)

@app.route('/')
def home(): return "running"

if __name__ == "__main__":
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
