from collections import defaultdict

ui_state = defaultdict(list)


def safe_clear_ui(bot, chat_id, message_ids):
    try:
        for mid in message_ids[-5:]:
            bot.delete_message(chat_id, mid)
    except Exception:
        pass
