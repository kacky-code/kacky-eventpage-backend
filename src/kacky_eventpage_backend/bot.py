from pathlib import Path

import discord
import yaml
from discord.ext import commands

TOKEN = ""
GUILD_ID = ""

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="THEREISnoFUCKINGprefix!", intents=intents)


@bot.event
async def on_ready():
    for guild in bot.guilds:
        if guild.name == GUILD_ID:
            break

    print(
        f"{bot.user} is connected to the following guild: \n"
        f"{guild.name} (id: {guild.id})"
    )

    # just trying to debug here
    for guild in bot.guilds:
        for member in guild.members:
            print(member.name, " ")

    # members = '\n - '.join([member.name for member in guild.members])
    # print(f'Guild Members:\n - {members}')
    # await guild.members[1].send("hey u")


def main():
    try:
        print(Path(__file__))
        with open(Path(__file__).parents[2] / "secrets.yaml") as b:
            conf = yaml.load(b, yaml.FullLoader)
    except FileNotFoundError:
        raise FileNotFoundError(
            "Bot needs a bot.py with 'token' and 'guild' keys, containing the token for"
            " the bot and the ID of the guild to connect to!"
        )
    TOKEN = conf["token"]
    GUILD_ID = conf["guild"]
    if TOKEN == "" or GUILD_ID == "":
        raise RuntimeError("Bad values in secrets.yaml!")
    bot.load_extension(
        "kacky_eventpage_backend.discord_notification.kacky_notifier_cog"
    )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
