from __future__ import annotations

import collections
import json
import os
import subprocess
import traceback
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path
from typing import TYPE_CHECKING

import discord
import requests
import sentry_sdk
from discord import app_commands
from discord.ext import commands

from core import database
from core.common import (
    ConsoleColors,
    Colors,
    Others,
    TechID,
    Emoji,
)
from core.logging_module import get_log

_log = get_log(__name__)


async def before_invoke_(ctx: commands.Context):
    q = database.CommandAnalytics.create(
        command=ctx.command.name,
        user=ctx.author.id,
        date=datetime.now(),
        command_type="regular",
        guild_id=ctx.guild.id,
    ).save()

    sentry_sdk.set_user(None)
    sentry_sdk.set_user({"id": ctx.author.id, "username": ctx.author.name})
    sentry_sdk.set_tag("username", f"{ctx.author.name}#{ctx.author.discriminator}")
    if ctx.command is None:
        sentry_sdk.set_context(
            "user",
            {
                "name": ctx.author.name,
                "id": ctx.author.id,
                "command": ctx.command,
                "guild": ctx.guild.name,
                "guild_id": ctx.guild.id,
                "channel": ctx.channel.name,
                "channel_id": ctx.channel.id,
            },
        )
    else:
        sentry_sdk.set_context(
            "user",
            {
                "name": ctx.author.name,
                "id": ctx.author.id,
                "command": "Unknown",
                "guild": ctx.guild.name,
                "guild_id": ctx.guild.id,
                "channel": ctx.channel.name,
                "channel_id": ctx.channel.id,
            },
        )


async def on_ready_(bot):
    now = datetime.now()
    query: database.CheckInformation = (
        database.CheckInformation.select()
        .where(database.CheckInformation.id == 1)
        .get()
    )

    if not query.PersistantChange:
        # bot.add_view(ViewClass(bot))

        query.PersistantChange = True
        query.save()

    if not os.getenv("USEREAL"):
        IP = os.getenv("DATABASE_IP")
        databaseField = f"{ConsoleColors.OKGREEN}Selected Database: External ({IP}){ConsoleColors.ENDC}"
    else:
        databaseField = (
            f"{ConsoleColors.FAIL}Selected Database: localhost{ConsoleColors.ENDC}\n{ConsoleColors.WARNING}WARNING: Not "
            f"recommended to use SQLite.{ConsoleColors.ENDC} "
        )

    try:
        p = subprocess.run(
            "git describe --always",
            shell=True,
            text=True,
            capture_output=True,
            check=True,
        )
        output = p.stdout
    except subprocess.CalledProcessError:
        output = "ERROR"

    # chat_exporter.init_exporter(bot)

    print(
        f"""
            ArasakaBot OS

            Bot Account: {bot.user.name} | {bot.user.id}
            {ConsoleColors.OKCYAN}Discord API Wrapper Version: {discord.__version__}{ConsoleColors.ENDC}
            {ConsoleColors.WARNING}ArasakaBot Version: {output}{ConsoleColors.ENDC}
            {databaseField}

            {ConsoleColors.OKCYAN}Current Time: {now}{ConsoleColors.ENDC}
            {ConsoleColors.OKGREEN}Cogs, libraries, and views have successfully been initialized.{ConsoleColors.ENDC}
            ==================================================
            {ConsoleColors.WARNING}Statistics{ConsoleColors.ENDC}

            Guilds: {len(bot.guilds)}
            Members: {len(bot.users)}
            """
    )


def initializeDB(bot):
    """
    Initializes the database, and creates the needed table data if they don't exist.
    """
    database.db.connect(reuse_if_open=True)
    CIQ = database.CheckInformation.select().where(database.CheckInformation.id == 1)

    if not CIQ.exists():
        database.CheckInformation.create(
            MasterMaintenance=False,
            guildNone=False,
            externalGuild=True,
            ModRoleBypass=True,
            ruleBypass=True,
            publicCategories=True,
            elseSituation=True,
            PersistantChange=False,
        )
        _log.info("Created CheckInformation Entry.")

    if len(database.Administrators) == 0:
        for person in bot.owner_ids:
            database.Administrators.create(discordID=person, TierLevel=4)
            _log.info("Created Administrator Entry.")
        database.Administrators.create(discordID=409152798609899530, TierLevel=4)

    query: database.CheckInformation = (
        database.CheckInformation.select()
        .where(database.CheckInformation.id == 1)
        .get()
    )
    query.PersistantChange = False
    query.save()
    database.db.close()


async def on_command_error_(bot, ctx: commands.Context, error: Exception):
    tb = error.__traceback__
    etype = type(error)
    exception = traceback.format_exception(etype, error, tb, chain=True)
    exception_msg = ""
    for line in exception:
        exception_msg += line

    error = getattr(error, "original", error)
    if ctx.command is not None:
        if ctx.command.name == "rule":
            return "No Rule..."

    if isinstance(error, (commands.CheckFailure, commands.CheckAnyFailure)):
        return

    if hasattr(ctx.command, "on_error"):
        return

    elif isinstance(error, (commands.CommandNotFound, commands.errors.CommandNotFound)):
        cmd = ctx.invoked_with
        cmds = [cmd.name for cmd in bot.commands]
        matches = get_close_matches(cmd, cmds)
        if len(matches) > 0:
            return await ctx.send(
                f'Command "{cmd}" not found, maybe you meant "{matches[0]}"?'
            )
        else:
            """return await ctx.send(
                f'Command "{cmd}" not found, use the help command to know what commands are available. '
                f"Some commands have moved over to slash commands, please check "
                f"url"
                f"for more updates! "
            )"""
            return await ctx.message.add_reaction("❌")

    elif isinstance(
        error, (commands.MissingRequiredArgument, commands.TooManyArguments)
    ):
        signature = f"{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}"

        em = discord.Embed(
            title="Missing/Extra Required Arguments Passed In!",
            description="You have missed one or several arguments in this command"
            "\n\nUsage:"
            f"\n`{signature}`",
            color=Colors.red,
        )
        em.set_thumbnail(url=bot.user.avatar.url)
        em.set_footer(
            text="Consult the Help Command if you are having trouble or call over a Bot Manager!"
        )
        return await ctx.send(embed=em)

    elif isinstance(
        error,
        (
            commands.MissingAnyRole,
            commands.MissingRole,
            commands.MissingPermissions,
            commands.errors.MissingAnyRole,
            commands.errors.MissingRole,
            commands.errors.MissingPermissions,
        ),
    ):
        em = discord.Embed(
            title="Invalid Permissions!",
            description="You do not have the associated role in order to successfully invoke this command! "
            "Contact an administrator/developer if you believe this is invalid.",
            color=Colors.red,
        )
        em.set_thumbnail(url=bot.user.avatar.url)
        em.set_footer(
            text="Consult the Help Command if you are having trouble or call over a Bot Manager!"
        )
        await ctx.send(embed=em)
        return

    elif isinstance(
        error,
        (commands.BadArgument, commands.BadLiteralArgument, commands.BadUnionArgument),
    ):
        signature = f"{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}"

        em = discord.Embed(
            title="Bad Argument!",
            description=f"Unable to parse arguments, check what arguments you provided."
            f"\n\nUsage:\n`{signature}`",
            color=Colors.red,
        )
        em.set_thumbnail(url=bot.user.avatar.url)
        em.set_footer(
            text="Consult the Help Command if you are having trouble or call over a Bot Manager!"
        )
        return await ctx.send(embed=em)

    elif isinstance(
        error, (commands.CommandOnCooldown, commands.errors.CommandOnCooldown)
    ):
        m, s = divmod(error.retry_after, 60)
        h, m = divmod(m, 60)

        msg = "This command cannot be used again for {} minutes and {} seconds".format(
            round(m), round(s)
        )

        embed = discord.Embed(
            title="Command On Cooldown", description=msg, color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    else:
        error_file = Path("error.txt")
        error_file.touch()
        with error_file.open("w") as f:
            f.write(exception_msg)
        embed = discord.Embed(
            title="Error Detected!",
            description="Seems like I've ran into an unexpected error!",
            color=Colors.red,
        )
        embed.add_field(
            name="Error Message",
            value=f"Check the console for more information.",
        )
        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text=f"Error: {str(error)}")
        await ctx.send(embed=embed)
    raise error