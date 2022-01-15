import discord
from discord.ext import commands

TOKEN = "OTI1Nzc2NDk0OTk3OTQyNDAy.YcyCjA.fKgOeXMxIvFzoNyfRZxt-DS-YFo"
GUILD_ID = "925785886774403073"

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    for guild in bot.guilds:
        if guild.name == GUILD_ID:
            break

    print(
        f'{bot.user} is connected to the following guild: \n' 
        f'{guild.name} (id: {guild.id})'
    )

    # just trying to debug here
    for guild in bot.guilds:
        for member in guild.members:
            print(member.name, ' ')

    #members = '\n - '.join([member.name for member in guild.members])
    #print(f'Guild Members:\n - {members}')
    #await guild.members[1].send("hey u")


bot.load_extension("discord_notification.kacky_notifier_cog")
bot.run(TOKEN)
