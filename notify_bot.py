import requests

BOT_TOKEN = "7938311608:AAHmzsTqnVJ7cVtStp2lmzGe2-1oj9LN1JM"
ADMIN_ID = 1311851277

with open("last_db_link.txt", "r") as f:
    link = f.read().strip()


def notify_bot():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": ADMIN_ID, "text": f"/auto_update_db {link}"}
    r = requests.post(url, data=data)
    print("✅ Bot xəbərdar edildi:", r.text)


if __name__ == "__main__":
    notify_bot()
