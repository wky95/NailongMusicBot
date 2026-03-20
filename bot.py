import discord
import os
from discord.ext import commands
import ctypes.util
import os
from dotenv import load_dotenv

if not discord.opus.is_loaded():
    try:
        if sys.platform == 'darwin':
            discord.opus.load_opus('/opt/homebrew/lib/libopus.dylib')
        elif sys.platform == 'linux':
            discord.opus.load_opus('libopus.so.0')
    except Exception as e:
        print(f"載入 Opus 失敗，語音功能可能無法使用: {e}")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=';', intents=intents)

# 啟動時自動載入 cogs 資料夾下的所有檔案
@bot.event
async def on_ready():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
            except commands.ExtensionAlreadyLoaded:
                pass
    print(f'{bot.user} 已上線！')

@bot.command()
@commands.is_owner()
async def reload(ctx, extension):
    try:
        await bot.reload_extension(f'cogs.{extension}')
        await ctx.send(f'已更新 {extension}')
    except commands.ExtensionNotLoaded:
        await bot.load_extension(f'cogs.{extension}')
        await ctx.send(f'已更新 {extension}')
    except Exception as e:
        await ctx.send(f'錯誤: {e}')

load_dotenv()
bot.run(os.getenv("DB_token"))
