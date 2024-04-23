import os
import time
from datetime import datetime
from distutils.util import strtobool

import peewee
import pytz
from dotenv import load_dotenv
from flask import Flask
from peewee import (
    AutoField,
    BigIntegerField,
    BooleanField,
    DateTimeField,
    IntegerField,
    Model,
    MySQLDatabase,
    SqliteDatabase,
    TextField,
    FloatField
)

from core.logging_module import get_log

load_dotenv()
_log = get_log(__name__)



"""
Change to a SqliteDatabase if you don't have any MySQL Credentials.
If you do switch, comment/remove the MySQLDatabase variable and uncomment/remove the # from the SqliteDatabase instance. 
"""

if os.getenv("DATABASE_IP") is None:
    db = SqliteDatabase("data.db")
    _log.info("No Database IP found in .env file, using SQLite!")

elif os.getenv("DATABASE_IP") is not None:
    # useDB = bool(input(f"{bcolors.WARNING}Do you want to use MySQL? (y/n)\n    > This option should be avoided if you are testing new database structures, do not use MySQL Production if you are testing table modifications.{bcolors.ENDC}"))
    db = SqliteDatabase("data.db")
    if not os.getenv("PyTestMODE"):
        _log.info(f"Successfully connected to the SQLite Database")
    else:
        _log.info(f"Testing environment detected, using SQLite Database")


def iter_table(model_dict: dict):
    """Iterates through a dictionary of tables, confirming they exist and creating them if necessary."""
    for key in model_dict:
        if not db.table_exists(key):
            db.connect(reuse_if_open=True)
            db.create_tables([model_dict[key]])
            db.close()
        else:
            db.connect(reuse_if_open=True)
            for column in model_dict[key]._meta.sorted_fields:
                if not db.column_exists(key, column.name):
                    db.create_column(key, column.name)
            db.close()


"""
DATABASE FILES

This file represents every database table and the model they follow. When fetching information from the tables, consult the typehints for possible methods!

"""


class BaseModel(Model):
    """Base Model class used for creating new tables."""

    class Meta:
        database = db


class Administrators(BaseModel):
    """
    Administrators:
    List of users who are whitelisted on the bot.

    `id`: AutoField()
    Database Entry

    `discordID`: BigIntegerField()
    Discord ID

    `TierLevel`: IntegerField()
    TIER LEVEL

    1 - Bot Manager\n
    2 - Admin\n
    3 - Sudo Admin\n
    4 - Owner
    """

    id = AutoField()
    discordID = BigIntegerField(unique=True)
    TierLevel = IntegerField(default=1)


class AdminLogging(BaseModel):
    """
    # AdminLogging:
    List of users who are whitelisted on the bot.

    `id`: AutoField()
    Database Entry

    `discordID`: BigIntegerField()
    Discord ID

    `action`: TextField()
    Command Name

    `content`: TextField()
    `*args` passed in

    `datetime`: DateTimeField()
    DateTime Object when the command was executed.
    """

    id = AutoField()
    discordID = BigIntegerField()
    action = TextField()
    content = TextField(default="N/A")
    datetime = DateTimeField(default=datetime.now())


class Blacklist(BaseModel):
    """
    # Blacklist:
    List of users who are blacklisted on the bot.

    `id`: AutoField()
    Database Entry

    `discordID`: BigIntegerField()
    Discord ID
    """

    id = AutoField()
    discordID = BigIntegerField(unique=True)


class CommandAnalytics(BaseModel):
    """
    #CommandAnalytics
    `id`: AutoField()
    Database Entry ID
    `command`: TextField()
    The command that was used.
    `user`: IntegerField()
    The user that used the command.
    `date`: DateTimeField()
    The date when the command was used.
    `command_type`: TextField()
    The type of command that was used.
    `guild_id`: BigIntegerField()
    The guild ID of the guild that the command was used in.
    """

    id = AutoField()
    command = TextField()
    date = DateTimeField()
    command_type = TextField()
    guild_id = BigIntegerField()
    user = BigIntegerField()


class CheckInformation(BaseModel):
    """
    # CheckInformation:
    List of users who are whitelisted on the bot.
    `id`: AutoField()
    Database Entry
    `MasterMaintenance`: BooleanField()
    Ultimate Check; If this is enabled no one except Permit 4+ users are allowed to use the bot.\n
    '>>> **NOTE:** This attribute must always have a bypass to prevent lockouts, otherwise this check will ALWAYS return False.
    `guildNone`: BooleanField()
    If commands executed outside of guilds (DMs) are allowed.
    `externalGuild`: BooleanField()
    If commands executed outside of the main guild (Staff Servers, etc) are allowed.
    `ModRoleBypass`: BooleanField()
    If commands executed inside of a public/general channel by a mod+ is allowed.
    `ruleBypass`: BooleanField()
    If the command *rule* is executed in public/general channels is allowed.
    `publicCategories`: BooleanField()
    If any command (except rule) inside of a public/general channel is allowed.
    `elseSituation`: BooleanField()
    Other situations will be defaulted to/as ...
    `PersistantChange`: BooleanField()
    If the discord bot has added its persistant buttons/views.
    """

    id = AutoField()

    MasterMaintenance = BooleanField()
    guildNone = BooleanField()
    externalGuild = BooleanField()
    publicCategories = BooleanField()
    elseSituation = BooleanField()
    PersistantChange = BooleanField()


class Warns(BaseModel):
    """
    # Warns:
    List of users who are warned on the bot.

    `id`: AutoField()
    Database Entry

    `discord_id`: BigIntegerField()
    Discord ID

    `warn_reason`: IntegerField()
    Number of warns
    """

    id = AutoField()
    discord_id = BigIntegerField(unique=False)
    moderator_id = BigIntegerField()
    warn_reason = TextField(default="No reason given.")
    datetime = DateTimeField(default=time.time())


class EventAnalytics(BaseModel):
    """
    # EventAnalytics

    `id`: AutoField()
    Database Entry | Event ID

    `event_id`: BigIntegerField()
    The event ID.

    `author_id`: BigIntegerField()
    The author of the event.

    `event_type`: TextField()
    The user who reacted to the event.

    `initial_reaction_count`: IntegerField()
    The initial reaction count of the event.

    `cancelled`: BooleanField()
    If the event was cancelled. | This doesn't apply to events that were cancelled before/during stage 0.
    > Canceled is defined as the event being cancelled during stage 1 where the `End Event` button was clicked before the prep time ended.
    """

    id = AutoField()
    event_id = BigIntegerField()
    author_id = BigIntegerField()
    event_type = TextField()
    initial_reaction_count = IntegerField()
    created_at = DateTimeField(default=datetime.now(tz=pytz.timezone("America/New_York")))
    end_at = DateTimeField(null=True)
    duration = IntegerField(null=True)
    cancelled = BooleanField(default=False)




class EventBlacklist(BaseModel):
    """
    # EventBlacklist

    `id`: AutoField()
    Database Entry ID

    `user_id`: BigIntegerField()
    The user ID of the user who is blacklisted from events.

    `reason`: TextField()
    The reason for the blacklist.
    """

    id = AutoField()
    user_id = BigIntegerField()
    reason = TextField()


class AutoRole(BaseModel):
    """
    # AutoRole

    `id`: AutoField()
    Database Entry ID

    `role_id`: BigIntegerField()
    The role ID of the role.

    `name`: TextField()
    The name of the event this role is related to.
    """

    id = AutoField()
    role_id = BigIntegerField()
    name = TextField()


class DiscordToRoblox(BaseModel):
    """
    # DiscordToRoblox

    `id`: AutoField()
    Database Entry ID

    `discord_id`: BigIntegerField()
    The discord ID of the user.

    `roblox_username`: TextField()
    The roblox ID of the user.
    """

    id = AutoField()
    discord_id = BigIntegerField()
    roblox_username = TextField()


class EventsHosted(BaseModel):
    """
    # EventsHosted

    `id`: AutoField()
    Database Entry ID

    `discord_id`: BigIntegerField()
    The discord ID of the host.

    `host_username`: TextField()
    The username of the host.

    `co_host_username`: TextField()
    The username of the co-host.

    `supervisor_username`: TextField()
    The username of the supervisor.

    `attendees`: TextField()
    The attendees of the event.

    `event_type`: TextField()
    The type of event hosted.

    `xp_awarded`: FloatField()
    The amount of XP awarded.

    `datetime`: DateTimeField()
    The date and time the event was hosted.

    `wedge_picture`: TextField()
    The URL of the wedge picture.
    """
    id = AutoField()
    discord_id = BigIntegerField()
    host_username = TextField()
    co_host_username = TextField(null=True)
    supervisor_username = TextField(null=True)
    attendees = TextField()
    event_type = TextField()
    xp_awarded = FloatField()
    datetime = DateTimeField(default=datetime.utcnow())
    wedge_picture = TextField()
    is_active = BooleanField(default=True)


app = Flask(__name__)


@app.before_request
def _db_connect():
    """
    This hook ensures that a connection is opened to handle any queries
    generated by the request.
    """
    db.connect()


@app.teardown_request
def _db_close(exc):
    """
    This hook ensures that the connection is closed when we've finished
    processing the request.
    """
    if not db.is_closed():
        db.close()


tables = {
    "Administrators": Administrators,
    "AdminLogging": AdminLogging,
    "Blacklist": Blacklist,
    "CommandAnalytics": CommandAnalytics,
    "CheckInformation": CheckInformation,
    "Warns": Warns,
    "EventAnalytics": EventAnalytics,
    "EventBlacklist": EventBlacklist,
    "AutoRole": AutoRole,
    "DiscordToRoblox": DiscordToRoblox,
    "EventsHosted": EventsHosted,
}

"""
This function automatically adds tables to the database if they do not exist,
however it does take a significant amount of time to run so the env variable 'PyTestMODE' should be 'False'
in development. 
"""

iter_table(tables)