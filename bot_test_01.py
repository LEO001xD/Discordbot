import discord
from discord.ext import commands
import yt_dlp as youtube_dl
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy

dx100 = commands.Bot(command_prefix='!', intents=discord.Intents.all())
Token = "YOUR_DISCORD_BOT_TOKEN"
SPOTIPY_CLIENT_ID = 'YOUR_SPOTIFY_CLIENT_ID'
SPOTIPY_CLIENT_SECRET = 'YOUR_SPOTIFY_CLIENT_SECRET'

# สร้าง Spotify API Client
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET))

# ปิดเสียงการรายงานข้อผิดพลาดบนคอนโซล
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ใช้ IPv4 เนื่องจากบางครั้ง IPv6 ทำให้เกิดปัญหา
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or dx100.loop
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Queue management
queue = []

def check_queue(ctx):
    if queue:
        next_song = queue.pop(0)
        ctx.voice_client.play(next_song, after=lambda e: (check_queue(ctx) if e else None))
        ctx.send(f'Now playing: {next_song.title}')

@dx100.event
async def on_ready():
    print('Ready!')
    botactivity = discord.Activity(type=discord.ActivityType.watching, name="yoki")
    await dx100.change_presence(activity=botactivity, status=discord.Status.do_not_disturb)

@dx100.command(name='invite', help='Invite Dx100(bot) to your server', category='invite')
async def invite(ctx):
    invite_link = "https://discord.com/oauth2/authorize?client_id=1246434317001949254&scope=bot&permissions=631119136948049"
    await ctx.send(f"Invite Dx100(bot) to your server: {invite_link}")

@dx100.command(name='join', help='Tells the Dx100(bot) to join the voice channel', category='join')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send(f'{ctx.message.author.name} is not connected to a voice channel')
        return
    else:
        channel = ctx.message.author.voice.channel
    await channel.connect()

@dx100.command(name='leave', help='To make Dx100(bot) leave the voice channel', category='leave')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("Dx100(bot) is not connected to a voice channel.")

@dx100.command(name='play', help='To play song', category='play')
async def play(ctx, url):
    try:
        if "open.spotify.com" in url:
            # เช็คว่า URL เป็นของ Spotify หรือไม่
            track_id = url.split("/")[-1].split('?')[0]  # ดึง Spotify ID จาก URL
            track_info = sp.track(track_id)  # รับข้อมูลเพลงจาก Spotify API
            track_name = track_info['name']
            artist_name = track_info['artists'][0]['name']
            query = f"{track_name} {artist_name} audio"

            # ค้นหาเพลงจาก YouTube โดยใช้ข้อมูลจาก Spotify
            data = ytdl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            player = await YTDLSource.from_url(data['url'], loop=dx100.loop, stream=True)
        else:
            # เป็น URL ของ YouTube
            player = await YTDLSource.from_url(url, loop=dx100.loop, stream=True)

        if ctx.voice_client.is_playing():
            queue.append(player)
            await ctx.send(f'Added to queue: {player.title}')
        else:
            ctx.voice_client.play(player, after=lambda e: check_queue(ctx))
            await ctx.send(f'Now playing: {player.title}')
    except Exception as e:
        await ctx.send(f'An error occurred: {str(e)}')

@dx100.command(name='pause', help='This command pauses the song', category='pause')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
    else:
        await ctx.send("Dx100(bot) is not playing anything at the moment.")

@dx100.command(name='resume', help='Resumes the song', category='resume')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send("Dx100(bot) was not playing anything before this. Use play command")

@dx100.command(name='stop', help='Stops the song', category='stop')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
    else:
        await ctx.send("Dx100(bot) is not playing anything at the moment.")

@dx100.command(name='skip', help='Skips the current song', category='skip')
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Skipped the current song.")
    else:
        await ctx.send("Dx100(bot) is not playing anything at the moment.")

@dx100.command(name='queue', help='Displays the current queue', category='queue')
async def queue_display(ctx):
    if queue:
        queue_titles = [song.title for song in queue]
        await ctx.send(f'Current queue:\n' + "\n".join(queue_titles))
    else:
        await ctx.send("The queue is empty.")

@dx100.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel is not None:
        txt = f'Welcome {member.mention}. Say hi!'
        await channel.send(txt)

    role_name = "คาวาอี้เกิวว🥸"
    role = discord.utils.get(member.guild.roles, name=role_name)
    if role:
        await member.add_roles(role)
        print(f"Assigned {role_name} role to {member.display_name}")
    else:
        print(f"Role {role_name} not found")

@dx100.event
async def on_member_remove(member):
    channel = member.guild.system_channel
    if channel is not None:
        txt = f'{member.mention} has left the server!'
        await channel.send(txt)

@dx100.event
async def on_message(message):
    if message.author == dx100.user:
        return
    
    if message.content.lower() == "hi":
        await message.channel.send(f'Hello, {message.author.mention}!')
    elif message.content.lower() == "hello":
        await message.channel.send(f'Hello, {message.author.mention}!')  
    await dx100.process_commands(message)

dx100.run(Token)
