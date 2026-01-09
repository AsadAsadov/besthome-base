from besthome_unified_bot import trigger_auto_update_db

ADMIN_ID = 1311851277

with open("last_db_link.txt", "r", encoding="utf-8") as f:
    link = f.read().strip()


def notify_bot():
    trigger_auto_update_db(ADMIN_ID, link)
    print("✅ Bot xəbərdar edildi")


if __name__ == "__main__":
    notify_bot()
