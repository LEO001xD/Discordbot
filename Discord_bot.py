import discord
from discord.ext import commands, tasks
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio

dx100 = commands.Bot(intents=discord.Intents.all(), command_prefix="!")
Token = "YOUR_DISCORD_BOT_TOKEN"

# Disable error reporting on console
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
    'source_address': '0.0.0.0'  
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

@dx100.event
async def on_ready():
    print('Ready!')
    botactivity = discord.Activity(type=discord.ActivityType.watching, name="yoki")
    await dx100.change_presence(activity=botactivity, status=discord.Status.do_not_disturb)
    idle_check.start()
    await clear_and_sync_commands()
    print(f'Logged in as {dx100.user}!')

async def clear_and_sync_commands():
    dx100.tree.clear_commands(guild=None)  # Clear global commands
    for guild in dx100.guilds:
        dx100.tree.clear_commands(guild=guild)  # Clear guild-specific commands

    # dx100.tree.add_command(invite)
    dx100.tree.add_command(play)
    dx100.tree.add_command(pause)
    dx100.tree.add_command(resume)
    dx100.tree.add_command(stop)
    dx100.tree.add_command(skip)
    dx100.tree.add_command(loop)
    dx100.tree.add_command(queue_display)
    dx100.tree.add_command(queue_clear)
    dx100.tree.add_command(leave)  # Add leave command

    await dx100.tree.sync()
    print("Commands cleared and synced!")

# @dx100.tree.command(name='invite', description='Invite Dx100(bot) to your server')
# async def invite(interaction: discord.Interaction):
#     invite_link = "https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot&permissions=631119136948049"
#     await interaction.response.send_message(f"**Invite Dx100(bot) to your server:** {invite_link}")

@dx100.tree.command(name='play', description='To play song')
async def play(interaction: discord.Interaction, url: str):
    voice_client = interaction.guild.voice_client
    channel = interaction.user.voice.channel

    if not interaction.user.voice:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    if voice_client and voice_client.channel != channel:
        await voice_client.disconnect()

    if not voice_client:
        await channel.connect()

    voice_client = interaction.guild.voice_client  # Refresh the voice client reference

    try:
        player = await YTDLSource.from_url(url, loop=dx100.loop, stream=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}")
        return

    guild_id = interaction.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    if guild_id not in loop_enabled:
        loop_enabled[guild_id] = False

    if voice_client.is_playing() or voice_client.is_paused():
        queues[guild_id].append(player)
        await interaction.response.send_message(f'**Added to queue:** `{player.title}`')
    else:
        global current_song
        current_song[guild_id] = player
        voice_client.play(player, after=lambda e: (check_queue(interaction) if not e else None))
        await interaction.response.send_message(f'**Now playing:** `{player.title}`')

@dx100.tree.command(name='pause', description='This command pauses the song')
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("**Paused the current song.**")
    else:
        await interaction.response.send_message("**Dx100(bot) is not playing anything at the moment.**")
    reset_idle_timer()

@dx100.tree.command(name='resume', description='Resumes the song')
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("**Resumed the song.**")
    else:
        await interaction.response.send_message("**Dx100(bot) was not playing anything before this. Use play command**")
    reset_idle_timer()

@dx100.tree.command(name='stop', description='Stops the song')
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("**Stopped the current song.**")
    else:
        await interaction.response.send_message("**Dx100(bot) is not playing anything at the moment.**")
    reset_idle_timer()

@dx100.tree.command(name='skip', description='Skips the current song')
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("**Skipped the current song.**")
    else:
        await interaction.response.send_message("**Dx100(bot) is not playing anything at the moment.**")
    reset_idle_timer()

@dx100.tree.command(name='loop', description='Toggles looping the current song')
async def loop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    voice_client = interaction.guild.voice_client

    if guild_id not in loop_enabled:
        loop_enabled[guild_id] = False

    if voice_client.is_playing() or voice_client.is_paused():
        loop_enabled[guild_id] = not loop_enabled[guild_id]
        status = "enabled" if loop_enabled[guild_id] else "disabled"
        if loop_enabled[guild_id]:
            await interaction.response.send_message(f"**Looping** `{current_song[guild_id].title}` **is now** `{status}`")
        else:
            await interaction.response.send_message(f"**Looping is now** `{status}`")
    else:
        await interaction.response.send_message("**Dx100(bot) is not playing anything to loop.**")

@dx100.tree.command(name='leave', description='Leaves the voice channel')
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        await interaction.response.send_message("**Disconnected from the voice channel.**")
    else:
        await interaction.response.send_message("**Dx100(bot) is not connected to a voice channel.**")

queues = {}
loop_enabled = {}
current_song = {}

def check_queue(interaction):
    guild_id = interaction.guild.id
    voice_client = interaction.guild.voice_client

    if guild_id not in queues:
        queues[guild_id] = []
    if guild_id not in loop_enabled:
        loop_enabled[guild_id] = False

    if loop_enabled[guild_id] and current_song.get(guild_id):
        player = YTDLSource(discord.FFmpegPCMAudio(current_song[guild_id].url, **ffmpeg_options), data=current_song[guild_id].data)
        voice_client.play(player, after=lambda e: (check_queue(interaction) if not e else None))
    elif queues[guild_id]:
        current_song[guild_id] = queues[guild_id].pop(0)
        player = YTDLSource(discord.FFmpegPCMAudio(current_song[guild_id].url, **ffmpeg_options), data=current_song[guild_id].data)
        voice_client.play(player, after=lambda e: (check_queue(interaction) if not e else None))
        asyncio.run_coroutine_threadsafe(interaction.channel.send(f'**Now playing:** `{current_song[guild_id].title}`'), dx100.loop)
    else:
        reset_idle_timer()

@dx100.tree.command(name='queue', description='Displays the current queue')
async def queue_display(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    if guild_id not in queues:
        queues[guild_id] = []

    if queues[guild_id]:
        queue_titles = [f"`{song.title}`" for song in queues[guild_id]]
        await interaction.response.send_message(f'**Current queue**\n' + "\n".join(queue_titles))
    else:
        await interaction.response.send_message("**The queue is empty.**")
    reset_idle_timer()

@dx100.tree.command(name='queueclear', description='Clears the current queue')
async def queue_clear(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    if guild_id not in queues:
        queues[guild_id] = []

    queues[guild_id].clear()
    await interaction.response.send_message("**Queue cleared.**")
    reset_idle_timer()

@dx100.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel is not None:
        txt = f'Welcome {member.mention}. Say hi!'
        await channel.send(txt)

    role_name = "ROLE_NAME"
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
    
    if message.content.lower() in ["hi", "hello"]:
        await message.channel.send(f'Hello, {message.author.mention}!')
    
    reset_idle_timer()
    await dx100.process_commands(message)

# Idle timer implementation
idle_time = 0
MAX_IDLE_TIME = 30  # 30 seconds

@tasks.loop(seconds=10)
async def idle_check():
    global idle_time
    idle_time += 10

    voice_clients = dx100.voice_clients
    for vc in voice_clients:
        # Check if there are no members in the voice channel
        if len(vc.channel.members) == 1:  # Only the bot is in the channel
            loop_enabled[vc.guild.id] = False  # Disable looping
            if not vc.is_playing() and not vc.is_paused() and idle_time >= MAX_IDLE_TIME:
                await vc.disconnect()
                idle_time = 0

def reset_idle_timer():
    global idle_time
    idle_time = 0

dx100.run(Token)
