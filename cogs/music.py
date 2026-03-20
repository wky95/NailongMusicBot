import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

# yt-dlp 串流設定
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        
        if "&list=" in url:
            url = url.split("&list")[0]

        def get_info():
            return ytdl.extract_info(url, download=False)
            
        data = await loop.run_in_executor(None, get_info)

        if 'entries' in data:
            data = data['entries'][0]

        audio_url = data['url']
        return cls(discord.FFmpegPCMAudio(audio_url, executable="ffmpeg", **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 儲存每個伺服器 (guild) 的音樂隊列
        self.queues = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    def play_next(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if len(queue) > 0:
            # 取出隊列中第一首歌
            next_song = queue.pop(0)
            url = next_song['url']
            title = next_song['title']
            
            # 使用同步包裝非同步函數碼，以便在 callback 內執行
            coro = self.play_song(ctx, url, title)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"Error in play_next: {e}")
        else:
            coro = ctx.send("音樂隊列已空，播放結束！")
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    async def play_song(self, ctx, url, pending_title=None):
        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            
            # 確保有語音客戶端
            if ctx.voice_client is None:
                await ctx.author.voice.channel.connect()

            ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
            await ctx.send(f'🎵 正在播放: **{player.title}**')
        except Exception as e:
            await ctx.send(f"發生錯誤: {e}")
            self.play_next(ctx) # 錯誤也跳下一首

    @commands.command(name='join', help='讓機器人加入語音頻道')
    async def join(self, ctx):
        if not ctx.message.author.voice:
            await ctx.send(f"{ctx.author.name}，你必須先加入一個語音頻道！")
            return
        
        channel = ctx.message.author.voice.channel
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
        await channel.connect()

    @commands.command(name='play', help='播放或加入隊列 YouTube 音樂 (輸入關鍵字或網址)')
    async def play(self, ctx, *, url):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("你必須先加入一個語音頻道！")
                return

        queue = self.get_queue(ctx.guild.id)

        async with ctx.typing():
            def get_fast_info():
                try:
                    search_str = f"ytsearch1:{url}" if not url.startswith('http') else url
                    return ytdl.extract_info(search_str, download=False, process=False)
                except Exception:
                    return None

            fast_info = await self.bot.loop.run_in_executor(None, get_fast_info)
            
            if not fast_info:
                await ctx.send("找不到相關歌曲。")
                return

            if 'entries' in fast_info:
                fast_info = list(fast_info['entries'])[0]

            song_info = {
                'url': fast_info.get('url') or fast_info.get('webpage_url') or url,
                'title': fast_info.get('title', 'Unknown Title')
            }

            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                queue.append(song_info)
                await ctx.send(f'📝 已加入隊列: **{song_info["title"]}** (目前隊列長度: {len(queue)})')
            else:
                await ctx.send('🔗 正在解析音訊串流連結...')
                await self.play_song(ctx, song_info['url'])

    @commands.command(name='skip', help='跳過當首歌曲')
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop() # 呼叫 stop 會自動觸發 after 的 play_next
            await ctx.send('⏭️ 已跳過當前歌曲！')
        else:
            await ctx.send("目前沒有正在播放的歌曲。")

    @commands.command(name='pause', help='暫停當前音樂')
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send('⏸️ 音樂已暫停！輸入 `!resume` 繼續播放。')
        else:
            await ctx.send("目前沒有正在播放的音樂可以暫停。")

    @commands.command(name='resume', help='繼續播放音樂')
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send('▶️ 繼續播放音樂！')
        else:
            await ctx.send("目前沒有被暫停的音樂。")
            
    @commands.command(name='queue', help='查看當前音樂隊列')
    async def show_queue(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if not queue:
            await ctx.send("目前隊列是空的。")
            return
            
        description = "**當前音樂隊列：**\n\n"
        for i, song in enumerate(queue, 1):
            description += f"**{i}.** {song['title']}\n"
        await ctx.send(description)

    @commands.command(name='search', help='搜尋 YouTube 音樂並提供選項清單')
    async def search(self, ctx, *, query):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("你必須先加入一個語音頻道！")
                return

        queue = self.get_queue(ctx.guild.id)

        async with ctx.typing():
            try:
                msg = await ctx.send(f'🔍 正在搜尋 **{query}** ...')
                
                search_opts = {'extract_flat': 'in_playlist', 'quiet': True}
                with youtube_dl.YoutubeDL(search_opts) as ytdl_search:
                    info = await self.bot.loop.run_in_executor(None, lambda: ytdl_search.extract_info(f"ytsearch5:{query}", download=False))
                
                if 'entries' not in info or not info['entries']:
                    await msg.edit(content="找不到任何結果。")
                    return
                
                entries = list(info['entries'])
                description = "請在 30 秒內輸入對應的**號碼** (1-5) 來選擇你要播放或加入隊列的歌曲：\n\n"
                for i, entry in enumerate(entries, 1):
                    title = entry.get('title', 'Unknown Title')
                    description += f"**{i}.** {title}\n"
                
                await msg.edit(content=description)

                def check(m):
                    return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

                try:
                    choice_msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                except asyncio.TimeoutError:
                    await ctx.send("⏳ 搜尋選擇已超時。")
                    return
                
                choice = int(choice_msg.content) - 1
                if choice < 0 or choice >= len(entries):
                    await ctx.send("❌ 無效的選擇，請重新搜尋。")
                    return
                
                selected_url = entries[choice].get('url')
                if not selected_url or not selected_url.startswith('http'):
                    selected_url = f"https://www.youtube.com/watch?v={entries[choice].get('id')}"

                song_info = {
                    'url': selected_url,
                    'title': entries[choice].get('title', 'Unknown Title')
                }

                if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                    queue.append(song_info)
                    await ctx.send(f'📝 已由搜尋將 **{song_info["title"]}** 加入隊列！ (目前隊列長度: {len(queue)})')
                else:
                    await ctx.send(f"🔗 正在解析選項 **{choice + 1}** 的串流連結...")
                    await self.play_song(ctx, song_info['url'])
                
            except Exception as e:
                await ctx.send(f"發生錯誤: {e}")

    @commands.command(name='stop', help='停止音樂、清空隊列並離開語音頻道')
    async def stop(self, ctx):
        self.queues[ctx.guild.id] = [] # 清空該群組的隊列
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
            await ctx.send("已清空隊列並離開語音頻道 👋")
        else:
            await ctx.send("機器人目前沒有連接到語音頻道。")

async def setup(bot):
    await bot.add_cog(Music(bot))
