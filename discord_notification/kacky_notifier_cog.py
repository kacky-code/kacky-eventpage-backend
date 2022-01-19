import logging

import discord
import requests
from discord.ext import tasks, commands

from db_ops.alarm_checker import AlarmChecker
from usermanagement.usermanager import UserMngr


class MyCog(commands.Cog):
    def __init__(self, bot):
        self.index = 0
        self.bot = bot
        self.adminlist = ["328138969243975680"] # corkscrew's discord id
        self.printer.start()
        self.loggername = "kk_discord_bot"
        self.logger = logging.getLogger(self.loggername)

        with open("bot.yaml") as b:
            conf = yaml.load(b, yaml.FullLoader)
        self.guild_id = conf["guild"]
        if self.guild_id = "":
            raise RuntimeError("Bad values in bot.yaml!")

    def cog_unload(self):
        self.printer.cancel()

    async def on_ready(self):
        print("cog ready")

    @tasks.loop(seconds=60.0)
    async def printer(self):
        # get next maps
        try:
            schedule_data = requests.get("https://kacky.dingens.me/data.json").json()
        except ConnectionError:
            self.logger.error("Could not connect to Scheduler API!")
            for userid in self.adminlist:
                try:
                    user = await self.bot.fetch_user(userid)
                    await user.send(f"Hey! kacky.dingens.me seems to have a problem! This also kills me, the bot :(")
                except discord.errors.HTTPException:
                    self.logger.error(f"Admin ID {userid} is a bad Discord ID!")
            return

        servers = schedule_data["serverinfo"]
        timeleft = schedule_data["timeleft"]
        ac = AlarmChecker({"logger_name": self.loggername})

        if timeleft[3] == -1:
            # stop, competition is over!
            return

        for server in servers:
            serv_name = list(server.keys())[0]
            # get time limit and find when 10 min remain (else use timelimit)
            serv_timelimit = server[serv_name][3]
            timeleft = serv_timelimit * 60 - server[serv_name][1]
            if serv_timelimit > 10:
                alarm_mark = 60 * 10 # 10 min in s
            else:
                alarm_mark = (serv_timelimit - 1) * 60  # timelimit - 1min in s
            if alarm_mark + 30 > timeleft > alarm_mark - 29:
                next_map = server[serv_name][2][1]
                discord_ids_for_alarm = ac.get_discord_ids_for_map(next_map)

                guild = self.bot.get_guild(self.guild_id)

                for userid in discord_ids_for_alarm:
                    self.logger.error(f"processing {userid}")
                    try:
                        # user = await self.bot.fetch_user(userid)
                        user = discord.utils.get(guild.members, name=userid.split("#")[0], discriminator=userid.split("#")[1])
                        self.logger.error(f"user: {user}    {user.id}")
                        if user is None:
                            # bad user credentials
                            self.logger.error(f"ID {userid} is a bad Discord ID!")
                            continue
                        await user.send(f"Hey, map **{next_map}** is coming up on **{serv_name}**! Roughly 10 min until it's played, glhf!")
                        # await user.send(f"For {serv_name}, the time limit is {serv_timelimit}. alarm at {alarm_mark}, time is at {server[serv_name][1]}")
                    except discord.errors.HTTPException:
                        self.logger.error(f"ID {userid} is a bad Discord ID!")
                    except IndexError:
                        self.logger.error(f"ID {userid} has bad format (no '#')!")


    @printer.before_loop
    async def before_printer(self):
        print('waiting...')
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(MyCog(bot))
