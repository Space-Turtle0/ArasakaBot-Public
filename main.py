"""
Copyright (C) SpaceTurtle0 - All Rights Reserved
 * Permission is granted to use this application as a code reference for educational purposes.
 * Written by SpaceTurtle#2587, October 2022
"""

__author__ = "SpaceTurtle#2587"
__author_email__ = "null"
__project__ = "Arasaka Discord Bot"

import faulthandler
import logging
import os
import random
import time
from datetime import datetime

import discord
from alive_progress import alive_bar
from discord import app_commands, Message
from discord.ext import commands
from discord.ext.commands import Context, errors
from discord.ext.commands._types import BotT
from discord_sentry_reporting import use_sentry
from dotenv import load_dotenv
from gtts import gTTS
from pygit2 import Repository, GIT_DESCRIBE_TAGS
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from core import database
from core.checks import is_botAdmin2
from core.common import get_extensions, PromotionButtons, ReviewInactivityView
from core.logging_module import get_log
from core.special_methods import (
    before_invoke_,
    initializeDB,
    on_ready_, on_command_error_,
)
from openai import OpenAI

load_dotenv()
faulthandler.enable()

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)

_log = get_log(__name__)
_log.info("Starting ArasakaBot...")


class ArasakaSlashTree(app_commands.CommandTree):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        blacklisted_users = [p.discordID for p in database.Blacklist]
        if interaction.user.avatar is None:
            await interaction.response.send_message("Due to a discord limitation, you must have an avatar set to use this command.")
            return False
        if interaction.user.id in blacklisted_users:
            await interaction.response.send_message(
                "You have been blacklisted from using commands!", ephemeral=True
            )
            return False
        return True

    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        print(error)
        # await on_app_command_error_(self.bot, interaction, error)
        raise error


class ArasakaBot(commands.Bot):
    """
    Generates a LosPollos Instance.
    """

    def __init__(self, uptime: time.time):
        super().__init__(
            command_prefix=commands.when_mentioned_or(os.getenv("AC_PREFIX")),
            intents=discord.Intents.all(),
            case_insensitive=True,
            tree_cls=ArasakaSlashTree,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="/help"
            ),
        )
        self.help_command = None
        #self.add_check(self.check)
        self._start_time = uptime

    async def on_ready(self):
        await on_ready_(self)

    async def on_message(self, message: discord.Message):
        if "<@582753069788430347>" in message.content and message.author != bot.user:
            if random.random() < 0.05:
                gif_link = "https://tenor.com/view/mexican-food-gif-20530505"
                await message.channel.send("ITS A TACO MAN!")
                await message.channel.send(gif_link)
        if "<@754395477503639592>" in message.content and message.author != bot.user:
            if random.random() < 0.1:
                gif_link = "https://tenor.com/view/messmer-the-impaler-shadow-of-the-erdtree-gif-13459686998123203300\nhttps://tenor.com/view/messmer-the-impaler-fire-snakes-gif-6139781798511829625"
                #await message.channel.send("Upon his name as Godfrey, First Elden Lord.")
                await message.channel.send(gif_link)

        await self.process_commands(message)

    async def on_command_error(self, context, exception) -> None:
        await on_command_error_(self, context, exception)

    async def setup_hook(self) -> None:
        with alive_bar(
            len(get_extensions()),
            ctrl_c=False,
            bar="bubbles",
            title="Initializing Cogs:",
        ) as bar:

            for ext in get_extensions():
                try:
                    await bot.load_extension(ext)
                except commands.ExtensionAlreadyLoaded:
                    await bot.unload_extension(ext)
                    await bot.load_extension(ext)
                except commands.ExtensionNotFound:
                    raise commands.ExtensionNotFound(ext)
                bar()

            # add persistence view button PromotionButtons
            bot.add_view(PromotionButtons(bot))
            bot.add_view(ReviewInactivityView(bot))

    async def is_owner(self, user: discord.User):
        """admin_ids = []
        query = database.Administrators.select().where(
            database.Administrators.TierLevel >= 3
        )
        for admin in query:
            admin_ids.append(admin.discordID)

        if user.id in admin_ids:
            return True"""

        return await super().is_owner(user)

    @property
    def version(self):
        """
        Returns the current version of the bot.
        """
        version = "1.0.1"

        return version

    @property
    def author(self):
        """
        Returns the author of the bot.
        """
        return __author__

    @property
    def author_email(self):
        """
        Returns the author email of the bot.
        """
        return __author_email__

    @property
    def start_time(self):
        """
        Returns the time the bot was started.
        """
        return self._start_time


bot = ArasakaBot(time.time())


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        database.CommandAnalytics.create(
            command=interaction.command.name,
            guild_id=interaction.guild.id,
            user=interaction.user.id,
            date=datetime.now(),
            command_type="slash",
        ).save()


if os.getenv("DSN_SENTRY") is not None:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,  # Capture info and above as breadcrumbs
        event_level=logging.ERROR,  # Send errors as events
    )

    # Traceback tracking, DO NOT MODIFY THIS
    use_sentry(
        bot,
        dsn=os.getenv("DSN_SENTRY"),
        traces_sample_rate=1.0,
        _experiments={
            "profiles_sample_rate": 1.0,
        },
        integrations=[FlaskIntegration(), sentry_logging],
    )


initializeDB(bot)

client = OpenAI(
    # This is the default and can be omitted
    api_key=os.getenv("OPENAI_API"),
)
# Creating a slash command in discord.py
@bot.tree.command(name="ask", description="Ask a question", guild=discord.Object(id=1143709921326682182))
async def ask(interaction: discord.Interaction, *, question: str):
    """if interaction.channel_id != 1216431006031282286:
        return await interaction.response.send_message("lil bro, you can't use this command here. take your ass to <#1216431006031282286>")"""
    if interaction.user.id == 582753069788430347:
        content = f"You are Arakaka, you are currently a member (rank A-2) in a roblox clan called Arasaka and the clan plays in a roblox game called Virus Border Roleplay (VBR). The user you're talking with, call him Taco Man. Answer as concisely as possible. Have a personality and feel free to be mean when needed. Current date: {datetime.now()}"
    else:
        content = f"You are Arakaka, you are currently a member (rank A-2) in a roblox clan called Arasaka and the clan plays in a roblox game called Virus Border Roleplay (VBR). Answer as concisely as possible but don't be obsessed with VBR, be a helpful person. Have a personality and feel free to be mean when needed. Current date: {datetime.now()}"
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {"role": "system",
             "content": content},
            {"role": "user", "content": question}
        ]
    )
    await interaction.response.send_message(response.choices[0].message.content)

@bot.command()
@is_botAdmin2
async def sayvc(ctx: commands.Context, *, text=None):
    if 1 == 1:
        await ctx.message.delete()

        if not text:
            # We have nothing to speak
            await ctx.send(f"Hey {ctx.author.mention}, I need to know what to say please.")
            return

        vc = ctx.voice_client  # We use it more then once, so make it an easy variable
        if not vc:
            # We are not currently in a voice channel
            await ctx.send("I need to be in a voice channel to do this, please use the connect command.")
            return

        # Lets prepare our text, and then save the audio file
        tts = gTTS(text=text, lang="en")
        tts.save("text.mp3")

        try:
            # Lets play that mp3 file in the voice channel
            vc.play(discord.FFmpegPCMAudio('text.mp3'), after=lambda e: print(f"Finished playing: {e}"))

            # Lets set the volume to 1
            vc.source = discord.PCMVolumeTransformer(vc.source)
            vc.source.volume = 1

        # Handle the exceptions that can occur
        except discord.ClientException as e:
            await ctx.send(f"A client exception occured:\n`{e}`")

        except TypeError as e:
            await ctx.send(f"TypeError exception:\n`{e}`")
    else:
        await ctx.send("You do not have permission to use this command.")


@bot.command()
async def connect(ctx, vc_id):
    try:
        ch = await bot.fetch_channel(vc_id)
        await ch.connect()
    except:
        await ctx.send("not a channel noob")
    else:
        await ctx.send("connected")

if __name__ == "__main__":
    bot.run(os.getenv("TOKEN"))