# 使用 pip 安装 python-telegram-bot 库
# pip install python-telegram-bot

from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

def echo(update: Update, context: CallbackContext) -> None:
    # 获取用户发送的消息文本
    message_text = update.message.text
    # 原封不动地回复相同的消息
    update.message.reply_text(message_text)

def main():
    # 替换 YOUR_TELEGRAM_BOT_TOKEN 为您从 BotFather 那里获得的令牌
    updater = Updater("YOUR_TELEGRAM_BOT_TOKEN")

    # 获取调度处理程序以注册处理程序
    dispatcher = updater.dispatcher

    # 在接收到文本消息时调用 "echo" 函数
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    # 启动机器人
    updater.start_polling()

    # 让机器人持续运行，直到您手动停止
    updater.idle()

if __name__ == '__main__':
    main()
