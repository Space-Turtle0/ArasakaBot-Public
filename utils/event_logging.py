import asyncio
import os
import typing
from datetime import datetime

import discord
import gspread
from discord import app_commands, ui, ButtonStyle
from discord.ext import commands
from oauth2client.service_account import ServiceAccountCredentials
from roblox import Client

from core import database
from core.common import (
    ButtonHandler, Colors, make_form, process_xp_updates, get_user_xp_data, RankHierarchy, ConfirmationView,
    PromotionButtons, InactivityModal, DischargeModel,
)
from core.logging_module import get_log

_log = get_log(__name__)

log_ch = 1145110858272346132
guild = 1143709921326682182

xp_log_ch = 1224907141060628532
officer_role_id = 1143736564002861146

rank_xp_thresholds = {
    'Initiate': 0,  # A-1
    'Junior Operative': 15,  # A-2
    'Operative': 30,  # A-3
    'Specialist': 50,  # A-4
    'Senior Agent': 85,  # A-5
    'Sergeant': 110,  # N-1
    #'Command Sergeant': 150,  # N-2
    #'Commander': 200,  # N-3
    # ... continue as needed
}

next_rank = {
    'Initiate': 'Junior Operative',
    'Junior Operative': 'Operative',
    'Operative': 'Specialist',
    'Specialist': 'Senior Agent',
    'Senior Agent': 'Sergeant',
    'Sergeant': 'RL',
    #'Command Sergeant': 'Commander',
    #'Commander': '🔒'
}

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('ArasakaBotCreds.json', scope)
client = gspread.authorize(creds)
sheet = client.open("Arasaka Corp. Database V2").sheet1


class EventLogging(commands.Cog):
    def __init__(self, bot: "ArasakaCorpBot"):
        self.bot: "ArasakaCorpBot" = bot
        self.client = Client(os.getenv("ROBLOX_SECURITY"))
        self.group_id = 33764698
        self.interaction = []

    XP = app_commands.Group(
        name="xp",
        description="Update XP for users in the spreadsheet.",
        guild_ids=[1223473430410690630, 1143709921326682182],
    )

    @app_commands.command(
        name="event_log",
        description="Log an event | Event Hosts Only",
    )
    @app_commands.guilds(1223473430410690630, 1143709921326682182)
    @app_commands.describe(
        host_username="Enter the event host's ROBLOX username (this should be yours).",
        event_type_opt="Select the event type you hosted.",
        proof_upload="Upload proof of the event. THIS IS NOT REQUIRED IF YOU WOULD RATHER UPLOAD A LINK AS PROOF.",
    )
    async def event_log(
            self,
            interaction: discord.Interaction,
            host_username: str,
            event_type_opt: typing.Literal["General Training", "Combat Training", "Agent Rally", "Gamenight", "Other"],
            proof_upload: discord.Attachment = None,
    ):
        bot_ref = self.bot
        event_host_role = discord.utils.get(interaction.guild.roles, id=1143736564002861146)
        #event_host_role = discord.utils.get(interaction.guild.roles, id=1223480830920229005) test role
        retired_hicom_role = discord.utils.get(interaction.guild.roles, id=1192942534968758342)

        if not any(role in interaction.user.roles for role in
                   [event_host_role, retired_hicom_role]) and interaction.user.id not in [
            409152798609899530]:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        EventLogForm = make_form(host_username, event_type_opt, proof_upload, bot_ref, sheet)

        await interaction.response.send_modal(EventLogForm(title="Event Logging Form"))

    @XP.command(description="Bulk update the XP of multiple users or a single user.")
    @app_commands.describe(
        usernames="Enter the usernames (COMMA SEPARATED) of the users you want to update.",
        action="Select whether you want to add or remove XP provided.",
        reason="Enter a reason for the XP update. (You can just say the event type)"
    )
    async def update(
            self,
            interaction: discord.Interaction,
            usernames: str,
            action: typing.Literal["add", "remove"],
            reason: str,
    ):
        xp_channel = await self.bot.fetch_channel(xp_log_ch)
        officer_role = discord.utils.get(interaction.guild.roles, id=officer_role_id)
        retired_hicom_role = discord.utils.get(interaction.guild.roles, id=1192942534968758342)

        # Permission check
        if not any(role in interaction.user.roles for role in
                   [officer_role, retired_hicom_role]) and interaction.user.id not in [
            409152798609899530]:  # List of allowed user IDs can be expanded
            return await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )

        # Acknowledge the command invocation
        await interaction.response.defer(ephemeral=True, thinking=True)

        usernames = [username.strip() for username in usernames.split(",")]
        await process_xp_updates(interaction, sheet, usernames, action, reason)

    @XP.command(description="Change the XP status of a user.")
    @app_commands.describe(
        username="Enter the username of the user you want to update.",
        action="Select the action you want to perform. (IN = Inactivity Notice, EX = Exempt, clear = Clear status: this will give them 0 for WP.)",
    )
    async def modify_status(
            self,
            interaction: discord.Interaction,
            username: str,
            action: typing.Literal["IN", "EX", "clear"],
    ):
        embed = discord.Embed(
            title="XP Status Modification",
            description="Modifying XP status for a single user...",
            color=discord.Color.dark_gold()
        )
        embed.add_field(
            name="Action",
            value=f"Executing change to {action} for the following user: {username}",
            inline=False,
        )
        embed.add_field(
            name="Console Output:",
            value="```diff\n1: In Progress...",
            inline=False,
        )
        line_number = 1

        if interaction.user.id == 882526905679626280:
            return await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )

        xp_channel = await self.bot.fetch_channel(xp_log_ch)
        officer_role = discord.utils.get(interaction.guild.roles, id=officer_role_id)
        retired_hicom_role = discord.utils.get(interaction.guild.roles, id=1192942534968758342)

        if not officer_role in interaction.user.roles and not retired_hicom_role in interaction.user.roles:
            if interaction.user.id == 409152798609899530:
                pass
            else:
                return await interaction.response.send_message(
                    "You do not have permission to use this command.",
                    ephemeral=True,
                )

        cell = sheet.find(username, case_sensitive=False)
        await interaction.response.send_message(embed=embed)

        if cell is None:
            field = embed.fields[1].value + f"\n- {line_number + 1}: Error: {username} not found in spreadsheet.\n```"
            embed.set_field_at(1, name="Console Output:", value=field)
            return await interaction.edit_original_response(embed=embed)

        user_row = cell.row
        weekly_points = sheet.cell(user_row, 10).value

        if action == "IN":
            new_weekly_points = "IN"
        elif action == "EX":
            new_weekly_points = "EX"
        else:
            new_weekly_points = 0

        values = [[new_weekly_points]]
        sheet.update(values, f'J{user_row}')

        field = embed.fields[
                    1].value + f"\n+ {line_number + 1}: Success: {username} -> **({action})** updated status!\n```"
        embed.set_field_at(1, name="Console Output:", value=field)
        embed.set_footer(text=f"Authorized by: {interaction.user.display_name} | XP STATUS UPDATE")
        await interaction.edit_original_response(embed=embed)

        await xp_channel.send(embed=embed)

    @XP.command(
        name="view",
        description="View XP and progress towards the next rank for yourself or another user."
    )
    @app_commands.describe(
        target_user="The user whose XP you want to view. Leave empty to view your own XP.",
        roblox_username="If the user has not linked/updated their Discord username to be their Roblox username, you can manually provide their Roblox username here."
    )
    async def _view(
            self,
            interaction: discord.Interaction,
            target_user: discord.Member = None,
            roblox_username: str = None,
    ):
        if target_user and roblox_username:
            confirmation_embed = discord.Embed(
                color=discord.Color.brand_red(),
                title="Too Many Arguments!",
                description=f"Hey {interaction.user.mention}, you provided both a discord user and a roblox username. "
                            f"Please provide only one!"
            )
            return await interaction.response.send_message(embed=confirmation_embed, ephemeral=True)
        await interaction.response.defer(thinking=True)

        if roblox_username:
            target_user = roblox_username
        elif target_user:
            target_user = target_user
        else:
            target_user = interaction.user
        promoted = False

        if isinstance(target_user, discord.Member) or isinstance(target_user, discord.User):
            user_data = await get_user_xp_data(target_user.display_name, sheet)
            if not user_data:
                query = database.DiscordToRoblox.select().where(
                    database.DiscordToRoblox.discord_id == target_user.id
                )
                if query.exists():
                    query = query.get()
                    roblox_username = query.roblox_username
                    user_data = await get_user_xp_data(roblox_username, sheet)
                    if user_data is None:
                        confirmation_embed = discord.Embed(
                            color=discord.Color.brand_red(),
                            title="Unknown Roblox Username",
                            description=f"Hey {interaction.user.mention}, I couldn't find the roblox username for data for "
                                        f"the user you specified."
                        )
                        confirmation_embed.add_field(
                            name="Resolutions",
                            value="It looks like you've already used /xp link but I still couldn't find the user's data. "
                                  "Try looking up the user's XP data manually in the spreadsheet and see if the username "
                                  "is correct **in there**. **Contact an Officer for further assistance if needed.**"
                                  " Feel free to re-run /xp link if you think you've entered the wrong username."
                        )
                        return await interaction.followup.send(embed=confirmation_embed, ephemeral=True)

                else:
                    confirmation_embed = discord.Embed(
                        color=discord.Color.brand_red(),
                        title="Unknown Roblox Username",
                        description=f"Hey {interaction.user.mention}, I couldn't find the roblox username for data for "
                                    f"the user you specified."
                    )
                    confirmation_embed.add_field(
                        name="Resolutions",
                        value="**For You:**\nIf you are trying to view your own XP, make sure you have linked your roblox "
                              "account with the `/xp link` command **OR** have your Roblox username as your Discord "
                              "nickname.\n\n**For Others**:\nIf you are trying to view someone else's XP, enter their "
                              "Roblox username in the `roblox_username` parameter **OR** tell them to follow the "
                              "**For You** steps.\n\nIf you've tried everything and still run into this issue, try "
                              "looking up the user's XP data manually in the spreadsheet and see if the username "
                              "is **correct in there**. **Contact an Officer for further assistance if needed.**",
                    )
                    return await interaction.followup.send(embed=confirmation_embed, ephemeral=True)
        else:
            user_data = await get_user_xp_data(target_user, sheet)
            if user_data is None:
                confirmation_embed = discord.Embed(
                    color=discord.Color.brand_red(),
                    title="Unknown Roblox Username",
                    description=f"Hey {interaction.user.mention}, I couldn't find the roblox username for data for "
                                f"the user you specified."
                )
                confirmation_embed.add_field(
                    name="Resolutions",
                    value="**For You:**\nIf you are trying to view your own XP, make sure you have linked your roblox "
                          "account with the `/xp link` command **OR** have your Roblox username as your Discord "
                          "nickname.\n\n**For Others**:\nIf you are trying to view someone else's XP, enter their "
                          "Roblox username in the `roblox_username` parameter **OR** tell them to follow the "
                          "**For You** steps.\n\nIf you've tried everything and still run into this issue, try "
                          "looking up the user's XP data manually in the spreadsheet and see if the username "
                          "is **correct in there**. **Contact an Officer for further assistance if needed.**",
                )
                return await interaction.followup.send(embed=confirmation_embed, ephemeral=True)

        current_rank_full_name = user_data['rank']
        total_xp = user_data['total_xp']
        ranks = ["Initiate", "Junior Operative", "Operative", "Specialist", "Senior Agent", "Sergeant", "RL"]
        next_rank_name_bool = True

        if current_rank_full_name not in ranks and current_rank_full_name != "Sergeant":
            next_rank_name = "🔒"
        elif current_rank_full_name == "Sergeant":
            next_rank_name = "🔒*"
        else:
            next_rank_name = next_rank.get(current_rank_full_name)

        # Create the progress bar
        if next_rank_name != '🔒' and next_rank_name != '🔒*':
            xp_to_next_rank = rank_xp_thresholds.get(next_rank_name, 0) - total_xp
            progress_percentage = (total_xp - rank_xp_thresholds[current_rank_full_name]) / (
                    rank_xp_thresholds[next_rank_name] - rank_xp_thresholds[current_rank_full_name])

            filled_slots = int(max(0, min(progress_percentage, 1)) * 10)
            empty_slots = 10 - filled_slots
            progress_bar = '🟥' * filled_slots + '⬛' * empty_slots + f" **{round(progress_percentage * 100, 2)}%**"
            if progress_percentage >= 1:
                promoted = True
                progress_bar = '🟥' * filled_slots + '⬛' * empty_slots + f" **100%** | **Pending Promotion**"

            # Quota Field (they meet quota if they have 8 or more WP)
            if user_data['weekly_xp'] == "IN":
                quota = "IN"
            elif user_data['weekly_xp'] == "EX":
                quota = "EX"
            else:
                weekly_xp = user_data['weekly_xp']
                if weekly_xp == "RH":
                    quota = f"✅ You're marked as being a new recruit, so you're exempt from the quota for this week!"
                else:
                    quota = f"✅ **{weekly_xp}**/8 WP" if float(weekly_xp) >= 8 else f"⬛ **{weekly_xp}**/8 WP"

        elif next_rank_name == "🔒*":
            progress_bar = '⬛' * 10 + '🔒'
            xp_to_next_rank = 'N/A'
            next_rank_name_bool = False
            next_rank_name = "N/A: **Rank Locked**\n\n**N-1** is the highest non-commissioned rank in the group. Congratulations on reaching the top! Contact an Officer for further instructions."

            weekly_xp = user_data['weekly_xp']
            quota = f"✅ **{weekly_xp}**/8 WP" if float(weekly_xp) >= 8 else f"⬛ **{weekly_xp}**/8 WP"

        else:
            progress_bar = '⬛' * 10 + '🔒'
            next_rank_name = 'N/A'
            xp_to_next_rank = 'N/A'
            if isinstance(target_user, discord.Member) or isinstance(target_user, discord.User):
                query = database.EventsHosted.select().where(
                    (database.EventsHosted.discord_id == target_user.id) & (database.EventsHosted.is_active == True)
                )
                if query.exists():
                    quota = f"✅ **{query.count()}**/4 Events Hosted" if query.count() >= 4 else f"⬛ **{query.count()}**/4 Events Hosted"
                else:
                    quota = f"⬛ **0**/4 Events Hosted"
            else:
                quota = "N/A: Can't be checked by roblox usernames, try using the `target_user` parameter instead."

        # Build the embed
        if isinstance(target_user, discord.Member) or isinstance(target_user, discord.User):
            target_user = target_user.display_name
        else:
            target_user = target_user

        embed = discord.Embed(
            title=f"{target_user}'s XP Progress",
            color=discord.Color.blue()
        )
        embed.add_field(name="Current Rank", value=current_rank_full_name, inline=False)
        embed.add_field(name="Next Rank", value=next_rank_name, inline=False)
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        embed.add_field(name="Met Quota?", value=quota, inline=False)
        if promoted:
            embed.add_field(name="Promotion FAQ", value="Congratulations on reaching the next rank's XP threshold! In "
                                                        "order for us to **fully** process you're promotion, "
                                                        "you'll need to submit a promotion request in "
                                                        "<#1225898217833496697>. The instructions for that can be "
                                                        "found here: "
                                                        "https://discord.com/channels/1143709921326682182/1225898217833496697/1226349662752211004",
                            inline=False)
        embed.set_footer(text=f"Total XP: {total_xp} XP | Weekly Points: {user_data['weekly_xp']} WP")
        if next_rank_name != 'N/A':
            if next_rank_name_bool:
                if not promoted:
                    embed.add_field(name="XP for Next Rank", value=f"{xp_to_next_rank} more XP needed for {next_rank_name}",
                                    inline=False)
                else:
                    embed.add_field(name="XP for Next Rank", value=f"Promotion to {next_rank_name} pending!", inline=False)
            else:
                embed.add_field(name="XP for Next Rank", value=f"🔒 Rank Locked", inline=False)
        else:
            embed.add_field(name="Status", value="🔒 Rank Locked", inline=False)

        # Send the embed as the interaction response
        await interaction.followup.send(embed=embed, ephemeral=False)

    @XP.command(
        name="link",
        description="Link your Discord account with your Roblox account."
    )
    @app_commands.describe(
        roblox_username="Enter your Roblox username to link your Discord account with it."
    )
    async def _link(
            self,
            interaction: discord.Interaction,
            roblox_username: str,
    ):
        id = 1156342512500351036
        await interaction.response.defer(ephemeral=True)
        query = database.DiscordToRoblox.select().where(
            database.DiscordToRoblox.discord_id == interaction.user.id
        )
        if query.exists():
            query = query.get()
            query.roblox_username = roblox_username
            query.save()

            confirmation_embed = discord.Embed(
                color=discord.Color.green(),
                title="Link Updated!",
                description=f"Hey {interaction.user.mention}, your Discord account has been successfully updated with the "
                            f"Roblox account `{roblox_username}`."
            )
            await interaction.followup.send(embed=confirmation_embed, ephemeral=True)

        else:
            query = database.DiscordToRoblox.create(
                discord_id=interaction.user.id,
                roblox_username=roblox_username
            )
            query.save()

            confirmation_embed = discord.Embed(
                color=discord.Color.green(),
                title="Link Successful!",
                description=f"Hey {interaction.user.mention}, your Discord account has been successfully linked with the "
                            f"Roblox account `{roblox_username}`."
            )
            await interaction.followup.send(embed=confirmation_embed, ephemeral=True)

    @XP.command(
        name="rank_manage",
        description="Manage the ranks of users in the Roblox Group."
    )
    async def rank_manage(
            self,
            interaction: discord.Interaction,
            reason: str,
            roblox_username: str = None,
            discord_username: discord.Member = None,
            action: typing.Literal["promote", "demote"] = None,
            target_rank: str = None,
    ):
        event_host_role = discord.utils.get(interaction.guild.roles, id=1156342512500351036)
        high_command = discord.utils.get(interaction.guild.roles, id=1143736740075552860)
        chancelor = discord.utils.get(interaction.guild.roles, id=1163157560237510696)
        big_boss = discord.utils.get(interaction.guild.roles, id=1158472045248651434)

        if not any(role in interaction.user.roles for role in
                   [event_host_role, high_command, chancelor, big_boss]) and interaction.user.id not in [
            409152798609899530]:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        target_user = discord_username or roblox_username
        if not target_user:
            return await interaction.response.send_message("You must provide a target user.", ephemeral=True)

        await interaction.response.defer()
        if action and target_rank:
            return await interaction.followup.send("You must provide either a target rank or an action, not both.")

        rank_obj = RankHierarchy(self.group_id, sheet)
        await rank_obj.set_officer_rank(interaction.user)

        group = await self.client.get_group(self.group_id)

        if isinstance(target_user, discord.Member):
            r_user = rank_obj.discord_to_roblox(target_user.id, group)
            confirm_name = target_user.display_name
        else:
            r_user = await group.get_member_by_username(target_user)
            confirm_name = target_user

        if action:
            if action == "promote":
                user_rank = await rank_obj.get_rank(r_user.name)
                target_rank = rank_obj.next_rank(user_rank)
            elif action == "demote":
                user_rank = await rank_obj.get_rank(r_user.name)
                target_rank = rank_obj.back_rank(user_rank)
        else:
            action = "change"

        roles = await group.get_roles()
        try:
            await group.set_role(r_user.id, next((role.id for role in roles if role.name == target_rank), None))
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"Failed to {action} {confirm_name} to {target_rank}.",
                color=discord.Colour.red(),
            )
            error_embed.add_field(name="Error", value=str(e))
            return await interaction.followup.send(embed=error_embed)
        else:
            confirmation_embed = discord.Embed(
                title="Rank Change",
                description=f"Successfully {action}d {confirm_name} to {target_rank}.",
                color=discord.Colour.green(),
            )
            await interaction.followup.send(embed=confirmation_embed)

            log_channel = self.bot.get_channel(xp_log_ch)
            log_embed = discord.Embed(
                title="Rank Change",
                description=f"Successfully {action}d {confirm_name} to {target_rank}.",
                color=discord.Colour.green(),
            )
            log_embed.set_footer(text=f"Authorized by: {interaction.user.display_name} | RANK CHANGE")
            await log_channel.send(embed=log_embed)

    @rank_manage.autocomplete('target_rank')
    async def rank_manage_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> typing.List[app_commands.Choice[str]]:
        raw_ranks = [
            "[COOT] Corporate Officer on Trial",
            "[O-1] Junior Corporate Field Officer",
            "[N-3] Commander",
            "[N-2] Command Sergeant",
            "[N-1] Sergeant",
            "[A-5] Senior Agent",
            "[A-4] Specialist",
            "[A-3] Operative",
            "[A-2] Junior Operative",
            "[A-1] Initiate",
            "Civilian"  # Lowest
        ]

        return [
            app_commands.Choice(name=rank, value=rank)
            for rank in raw_ranks if current.lower() in rank.lower()
        ]

    @XP.command(
        name="request_rank_change",
        description="Need a rank update in the group? Use this command to request a rank change!"
    )
    #@app_commands.guilds(1223473430410690630, 1143709921326682182)
    async def request_rank_change(
            self,
            interaction: discord.Interaction,
            rank_requesting: str,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        rank_obj = RankHierarchy(self.group_id, sheet)
        group = await self.client.get_group(self.group_id)
        r_user = rank_obj.discord_to_roblox(interaction.user.id, group)
        regular_user = await self.client.get_user(r_user.id)
        user_rank = await rank_obj.get_rank(regular_user.name)

        user_data = await get_user_xp_data(regular_user.name, sheet)

        """
        Username:
        Current Rank:
        Current XP: 
        Rank requesting: 
        Proof of your XP: (Must contain the full pillar: Username, WP, TP, etc.) 
        """

        username = regular_user.name
        print(username)
        current_rank = user_rank
        current_xp = user_data['total_xp']
        rank_requesting = rank_requesting
        proof_of_xp = f"Column Readout: {username}, {str(user_data['total_xp'])} TP, {str(user_data['weekly_xp'])} WP"

        xp_needed = rank_xp_thresholds.get(rank_requesting, 0) - current_xp
        if xp_needed > 0:
            xp_field = f"❌ | {xp_needed} more XP needed for {rank_requesting}."
        else:
            xp_field = f"✅ | Met the XP requirement for {rank_requesting}."

        embed = discord.Embed(
            title="Rank Change Request",
            description="Please review the information below and confirm that you would like to submit this request.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Username", value=username)
        embed.add_field(name="Current Rank", value=current_rank)
        embed.add_field(name="Current XP", value=current_xp)
        embed.add_field(name="Rank Requested", value=rank_requesting)
        embed.add_field(name="Proof of XP", value=proof_of_xp)
        embed.add_field(name="XP Requirement", value=xp_field)
        embed.set_footer(text="Please confirm that you would like to submit this request.")

        view = ConfirmationView()
        message: discord.WebhookMessage = await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        await view.wait()
        if view.value is None:
            return await message.edit(content="Request cancelled.", view=None, embed=embed)

        if view.value is True:
            log_channel = self.bot.get_channel(1225898217833496697)
            log_embed = discord.Embed(
                title="Rank Change Request",
                description=f"Requested by {interaction.user.mention}",
                color=discord.Color.blue()
            )

            log_embed.add_field(name="Username", value=username)
            log_embed.add_field(name="Current Rank", value=current_rank)
            log_embed.add_field(name="Current XP", value=current_xp)
            log_embed.add_field(name="Rank Requested", value=rank_requesting)
            log_embed.add_field(name="Proof of XP", value=proof_of_xp)
            log_embed.set_footer(text=f"Requested by: {interaction.user.display_name} | RANK CHANGE REQUEST")
            await log_channel.send(embed=log_embed, view=PromotionButtons(self.bot))

            await message.edit(content="Request submitted successfully.", view=None, embed=embed)
        else:
            await message.edit(content="Request cancelled.", view=None, embed=embed)

    @request_rank_change.autocomplete('rank_requesting')
    async def request_rank_change_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> typing.List[app_commands.Choice[str]]:
        raw_ranks = [
            "[N-3] Commander",
            "[N-2] Command Sergeant",
            "[N-1] Sergeant",
            "[A-5] Senior Agent",
            "[A-4] Specialist",
            "[A-3] Operative",
            "[A-2] Junior Operative",
            "[A-1] Initiate",
            "Civilian"  # Lowest
        ]

        return [
            app_commands.Choice(name=rank, value=rank)
            for rank in raw_ranks if current.lower() in rank.lower()
        ]

    @XP.command(
        name="request_inactivity_notice",
        description="Submit an inactivity notice if you'll be temporarily unavailable."
    )
    async def request_inactivity(
            self,
            interaction: discord.Interaction
    ):
        # Creating and sending a modal to collect inactivity details
        modal = InactivityModal(self.bot)
        await interaction.response.send_modal(modal)

    @XP.command(
        name="request_discharge",
        description="Submit a discharge request if you'd like to leave."
    )
    async def request_discharge(
            self,
            interaction: discord.Interaction
    ):
        # Creating and sending a modal to collect discharge details
        modal = DischargeModel(self.bot)
        await interaction.response.send_modal(modal)

    @XP.command(
        name="reset_officer_quota",
        description="Reset the officer quota for the week. | HICOM+ ONLY"
    )
    async def reset_officer_quota(
            self,
            interaction: discord.Interaction
    ):
        HICOM = discord.utils.get(interaction.guild.roles, id=1143736740075552860)
        BIGBOSS = discord.utils.get(interaction.guild.roles, id=1163157560237510696)
        ClanLeader = discord.utils.get(interaction.guild.roles, id=1158472045248651434)
        if not any(role in interaction.user.roles for role in
                   [HICOM, BIGBOSS, ClanLeader]) and interaction.user.id not in [409152798609899530]:
            return await interaction.response.send_message("You do not have permission to use this command.",
                                                           ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)

        for row in database.EventsHosted:
            row.is_active = False
            row.save()

        await interaction.followup.send("✅| Officer quota has been reset for the week.")

    @XP.command(
        name="blacklist",
        description="Blacklist a user from the group. | HICOM+ ONLY"
    )
    async def blacklist(
            self,
            interaction: discord.Interaction,
            discord_user: discord.Member,
            roblox_username: str,
            reason: str,
            appealable: bool,
            end_date: str = "-"
    ):
        HICOM = discord.utils.get(interaction.guild.roles, id=1143736740075552860)
        BIGBOSS = discord.utils.get(interaction.guild.roles, id=1163157560237510696)
        ClanLeader = discord.utils.get(interaction.guild.roles, id=1158472045248651434)
        if not any(role in interaction.user.roles for role in
                   [HICOM, BIGBOSS, ClanLeader]) and interaction.user.id not in [409152798609899530]:
            return await interaction.response.send_message("You do not have permission to use this command.",
                                                           ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        kicked = False
        dmed = False
        error_message = "N/A"

        group = await self.client.get_group(self.group_id)
        user = await group.get_member_by_username(roblox_username)
        try:
            await user.kick()
            kicked = True
        except Exception as e:
            error_message = e

        # sheet update now
        workspace = client.open("Arasaka Corp. Database V2").worksheet("Blacklists")
        today_date = datetime.now().strftime("%m/%d/%Y")

        def next_available_row(worksheet):
            return len(worksheet.col_values(2)) + 1

        # status calculation
        if end_date == "-":
            status = "PERMANENT"
        else:
            status = "BLACKLISTED"
        reason += " | Appealable: " + str(appealable)
        values = [[roblox_username, "", today_date, end_date, status, reason]]
        workspace.update(f'A{next_available_row(workspace)}:F{next_available_row(workspace)}', values)

        try:
            await discord_user.send(f"You have been blacklisted from Arasaka Corp. for the following reason: {reason}\n**Appealable:** {appealable} | **End Date:** {end_date}\n\nForward any questions to {interaction.user.mention}.")
            dmed = True
        except discord.Forbidden:
            pass
        await discord_user.ban(reason=f"User {roblox_username} has been blacklisted from the group for the following reason: {reason} by {interaction.user.display_name}")

        # make en embed detailing what it was able to do and what it wasn't
        embed = discord.Embed(
            title="Blacklist Report",
            color=discord.Color.red()
        )
        embed.add_field(name="User Kicked from Roblox Group", value="✅" if kicked else f"❌ | {error_message}")
        embed.add_field(name="User DM'd", value="✅" if dmed else "❌", inline=False)
        embed.add_field(name="User Banned from Discord", value="✅", inline=False)
        embed.add_field(name="Appealable", value="✅" if appealable else "❌", inline=False)
        embed.add_field(name="Blacklist Reason", value=reason, inline=False)
        embed.set_footer(text=f"Authorized by: {interaction.user.display_name} | BLACKLIST")
        await interaction.followup.send(embed=embed)

        log_channel = self.bot.get_channel(xp_log_ch)
        await log_channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventLogging(bot))
