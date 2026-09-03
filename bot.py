#!/usr/bin/env python3
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = '你的完整Token'  # 换成你的真实Token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot 正常运行！")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("🤖 测试 Bot 已启动...")
    app.run_polling()

if __name__ == "__main__":
    main()
