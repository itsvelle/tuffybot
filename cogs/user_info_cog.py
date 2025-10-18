import discord
from discord.ext import commands
from discord import AllowedMentions, ui, app_commands
from datetime import datetime, timedelta, timezone


class UserInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="userinfo", description="Displays detailed information about a user."
    )
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        """Displays detailed information about a user."""
        if member is None:
            member = interaction.user

        ctx = await commands.Context.from_interaction(interaction)

        # Fetch the member to ensure up-to-date data, especially for guild members
        cached = ctx.guild.get_member(member.id) if ctx.guild else None
        member = cached or member  # keep presence if we have it

        # only hit the API if we still need guild-specific data that might be stale
        if ctx.guild and member is not None and member.joined_at is None:
            try:
                member = await ctx.guild.fetch_member(member.id)  # roles/nick/etc.
            except discord.NotFound:
                await interaction.response.send_message(
                    "Could not find the specified member in this server.",
                    ephemeral=True,
                )
                return
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    f"An error occurred while fetching member data: `{e}`",
                    ephemeral=True,
                )
                return

        username_discriminator = (
            f"{member.name}#{member.discriminator}"
            if member.discriminator != "0"
            else member.name
        )
        created_at_str = member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        joined_at_str = (
            member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if member.joined_at
            else "N/A"
        )

        roles = [
            role.mention for role in reversed(member.roles) if role.name != "@everyone"
        ]
        roles_str = ", ".join(roles) if roles else "None"
        if len(roles_str) > 1000:  # Discord limits field values
            roles_str = roles_str[:997] + "..."

        status_str = str(member.status).title()
        activity_str = (
            f"Playing {member.activity.name}"
            if member.activity and member.activity.type is discord.ActivityType.playing
            else (
                f"Streaming {member.activity.name}"
                if member.activity
                and member.activity.type is discord.ActivityType.streaming
                else (
                    f"Listening to {member.activity.title}…"
                    if member.activity
                    and member.activity.type is discord.ActivityType.listening
                    else (
                        f"Watching {member.activity.name}"
                        if member.activity
                        and member.activity.type is discord.ActivityType.watching
                        else (
                            f"{member.activity.emoji} {member.activity.state}".strip()
                            if member.activity
                            and member.activity.type is discord.ActivityType.custom
                            else "None"
                        )
                    )
                )
            )
        )

        # Badges / Flags
        flags = member.public_flags  # this is a PublicUserFlags instance
        badges = [name.replace("_", " ").title() for name, enabled in flags if enabled]
        badges_str = ", ".join(badges) or "None"

        # Pronouns
        pronouns_str = getattr(member, "pronouns", "N/A")  # API v10-beta

        # Avatar Type
        avatar_type = (
            "GIF" if member.avatar and member.avatar.is_animated() else "Static"
        )

        # --- FIXED: use aware UTC datetime for “now” ---
        now_utc = datetime.now(timezone.utc)

        # Account Age
        account_age = now_utc - member.created_at
        account_age_str = (
            f"{account_age.days // 365} years, {(account_age.days % 365) // 30} months"
        )

        # Join Position
        join_position_str = "N/A"
        if ctx.guild and member.joined_at:
            sorted_members = sorted(
                ctx.guild.members,
                key=lambda m: (
                    m.joined_at
                    if m.joined_at
                    else datetime.min.replace(tzinfo=timezone.utc)
                ),
            )
            try:
                join_position_str = (
                    f"{sorted_members.index(member) + 1} of {len(sorted_members)}"
                )
            except ValueError:
                pass  # Member not found in sorted list (should not happen)

        # Server Boost Info
        boost_str = "Not boosting"
        if member.premium_since:
            # calculate months of boosting
            months = (now_utc - member.premium_since).days // 30
            boost_str = f"Boosting for {months} month{'s' if months != 1 else ''}"
        elif (
            ctx.guild
            and discord.utils.get(member.roles, id=ctx.guild.premium_subscriber_role.id)
            in member.roles
        ):
            boost_str = "Boosting (time unknown)"

        # Top / Hoisted Role
        top_role_str = (
            member.top_role.mention
            if member.top_role and member.top_role.name != "@everyone"
            else "None"
        )

        # Key Permissions
        key_permissions = []
        if member.guild_permissions.administrator:
            key_permissions.append("Administrator")
        if member.guild_permissions.manage_channels:
            key_permissions.append("Manage Channels")
        if member.guild_permissions.manage_guild:
            key_permissions.append("Manage Server")
        if member.guild_permissions.kick_members:
            key_permissions.append("Kick Members")
        if member.guild_permissions.ban_members:
            key_permissions.append("Ban Members")
        if member.guild_permissions.moderate_members:
            key_permissions.append("Moderate Members")
        if member.guild_permissions.manage_messages:
            key_permissions.append("Manage Messages")
        permissions_str = ", ".join(key_permissions) or "None"

        # Timeout Status
        timeout_str = "Not timed out"
        if member.timed_out_until:
            until_time = member.timed_out_until  # this is tz-aware
            time_left = until_time - now_utc
            if time_left > timedelta(0):
                hours, remainder = divmod(int(time_left.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                timeout_str = f"Timed out for {hours}h {minutes}m {seconds}s"
            else:
                timeout_str = "Timeout expired"

        # Device Status
        device_map = {
            discord.Status.online: "🟢",
            discord.Status.idle: "🌙",
            discord.Status.dnd: "⛔",
            discord.Status.offline: "⚫",
        }
        devices = []
        if member.desktop_status != discord.Status.offline:
            devices.append(f"Desktop {device_map.get(member.desktop_status, '⚫')}")
        if member.mobile_status != discord.Status.offline:
            devices.append(f"Mobile {device_map.get(member.mobile_status, '⚫')}")
        if member.web_status != discord.Status.offline:
            devices.append(f"Web {device_map.get(member.web_status, '⚫')}")
        device_status_str = ", ".join(devices) or "Offline"

        # Banner asset (requires an additional API call)
        banner_asset = member.banner
        if banner_asset is None:
            try:
                fetched_user = await self.bot.fetch_user(member.id)
            except discord.HTTPException:
                fetched_user = None
            if fetched_user:
                banner_asset = fetched_user.banner

        # --- UI Components v2 View ---
        class UserInfoView(ui.LayoutView):
            def __init__(self, target_member: discord.Member):
                super().__init__(timeout=180)  # 3 minutes timeout

                main_container = ui.Container(
                    accent_colour=target_member.color or discord.Color.default()
                )
                self.add_item(main_container)

                # Banner
                if banner_asset:
                    banner_gallery = ui.MediaGallery()
                    banner_gallery.add_item(
                        media=banner_asset.url,
                        description="User Banner",
                    )
                    main_container.add_item(banner_gallery)

                # Header Section with Avatar
                header_section = ui.Section(
                    accessory=ui.Thumbnail(
                        media=target_member.display_avatar.url,
                        description="User Avatar",
                    )
                )
                main_container.add_item(header_section)
                header_section.add_item(
                    ui.TextDisplay(f"**{target_member.display_name}**")
                )
                header_section.add_item(
                    ui.TextDisplay(
                        f"({username_discriminator}) - ID: {target_member.id}"
                    )
                )

                main_container.add_item(
                    ui.Separator(spacing=discord.SeparatorSpacing.small)
                )

                # Account & Profile
                main_container.add_item(
                    ui.TextDisplay(
                        f"**Account Created:** {created_at_str} ({account_age_str} ago)"
                    )
                )
                main_container.add_item(
                    ui.TextDisplay(f"**Avatar Type:** {avatar_type}")
                )
                main_container.add_item(ui.TextDisplay(f"**Badges:** {badges_str}"))
                if pronouns_str != "N/A":
                    main_container.add_item(
                        ui.TextDisplay(f"**Pronouns:** {pronouns_str}")
                    )

                main_container.add_item(
                    ui.Separator(spacing=discord.SeparatorSpacing.small)
                )

                # Guild-specific
                if ctx.guild:
                    main_container.add_item(
                        ui.TextDisplay(f"**Joined Server:** {joined_at_str}")
                    )
                    main_container.add_item(
                        ui.TextDisplay(f"**Join Position:** {join_position_str}")
                    )
                    main_container.add_item(
                        ui.TextDisplay(f"**Server Boost:** {boost_str}")
                    )
                    main_container.add_item(
                        ui.TextDisplay(f"**Top Role:** {top_role_str}")
                    )
                    main_container.add_item(
                        ui.TextDisplay(f"**Key Permissions:** {permissions_str}")
                    )
                    main_container.add_item(
                        ui.TextDisplay(f"**Timeout Status:** {timeout_str}")
                    )
                    if target_member.nick:
                        main_container.add_item(
                            ui.TextDisplay(f"**Nickname:** {target_member.nick}")
                        )

                    main_container.add_item(
                        ui.Separator(spacing=discord.SeparatorSpacing.small)
                    )

                # Status & Activity
                main_container.add_item(ui.TextDisplay(f"**Status:** {status_str}"))
                main_container.add_item(
                    ui.TextDisplay(f"**Device Status:** {device_status_str}")
                )
                main_container.add_item(ui.TextDisplay(f"**Activity:** {activity_str}"))

                # Roles
                main_container.add_item(
                    ui.Separator(spacing=discord.SeparatorSpacing.small)
                )
                main_container.add_item(ui.TextDisplay(f"**Roles ({len(roles)}):**"))
                if roles:
                    main_container.add_item(ui.TextDisplay(roles_str))
                else:
                    main_container.add_item(ui.TextDisplay("None"))

                # Voice State
                if target_member.voice:
                    main_container.add_item(
                        ui.Separator(spacing=discord.SeparatorSpacing.small)
                    )
                    main_container.add_item(
                        ui.TextDisplay(
                            f"**Voice Channel:** {target_member.voice.channel.mention if target_member.voice.channel else 'Not in a channel'}"
                        )
                    )
                    voice_state_details = []
                    if target_member.voice.self_mute:
                        voice_state_details.append("Muted (Self)")
                    if target_member.voice.self_deaf:
                        voice_state_details.append("Deafened (Self)")
                    if target_member.voice.mute:
                        voice_state_details.append("Muted (Server)")
                    if target_member.voice.deaf:
                        voice_state_details.append("Deafened (Server)")
                    if target_member.voice.self_stream:
                        voice_state_details.append("Streaming")
                    if target_member.voice.self_video:
                        voice_state_details.append("Video On")
                    if voice_state_details:
                        main_container.add_item(
                            ui.TextDisplay(
                                f"**Voice State:** {', '.join(voice_state_details)}"
                            )
                        )

        try:
            view = UserInfoView(member)
            await interaction.response.send_message(
                view=view,
                ephemeral=False,
                allowed_mentions=AllowedMentions(
                    roles=False, users=False, everyone=False
                ),
            )
        except Exception as e:
            import traceback

            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while creating the user info display: `{e}`",
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.__class__.__name__} cog has been loaded.")


async def setup(bot: commands.Bot):
    await bot.add_cog(UserInfoCog(bot))
