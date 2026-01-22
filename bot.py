import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
from dotenv import load_dotenv

from school21_api import School21API
from database import (
    init_database,
    add_verified_user,
    get_user_by_discord_id,
    is_login_taken
)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
S21_USERNAME = os.getenv("S21_USERNAME")
S21_PASSWORD = os.getenv("S21_PASSWORD")

# Role IDs
PEER_ROLE_ID = int(os.getenv("PEER_ROLE_ID", 0))
PHOENIX_ROLE_ID = int(os.getenv("PHOENIX_ROLE_ID", 0))
DRAGON_ROLE_ID = int(os.getenv("DRAGON_ROLE_ID", 0))
MINOTAUR_ROLE_ID = int(os.getenv("MINOTAUR_ROLE_ID", 0))
PEGASUS_ROLE_ID = int(os.getenv("PEGASUS_ROLE_ID", 0))

# Coalition name to role ID mapping
COALITION_ROLES = {
    "phoenix": PHOENIX_ROLE_ID,
    "dragon": DRAGON_ROLE_ID,
    "minotaur": MINOTAUR_ROLE_ID,
    "pegasus": PEGASUS_ROLE_ID,
    # Russian names
    "феникс": PHOENIX_ROLE_ID,
    "дракон": DRAGON_ROLE_ID,
    "минотавр": MINOTAUR_ROLE_ID,
    "пегас": PEGASUS_ROLE_ID,
}

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
s21_api: School21API = None


def get_coalition_role_id(coalition_name: str) -> int:
    """Get role ID for a coalition name."""
    if not coalition_name:
        return 0
    name_lower = coalition_name.lower()
    for key, role_id in COALITION_ROLES.items():
        if key in name_lower:
            return role_id
    return 0


@bot.event
async def on_ready():
    global s21_api
    logger.info(f"Bot logged in as {bot.user}")

    # Initialize database
    await init_database()

    # Initialize School 21 API
    s21_api = School21API(S21_USERNAME, S21_PASSWORD)

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")


@bot.tree.command(name="verify", description="Verify your School 21 account")
@app_commands.describe(login="Your School 21 login (nickname)")
async def verify(interaction: discord.Interaction, login: str):
    """Verify user with their School 21 login."""
    await interaction.response.defer(ephemeral=True)

    user = interaction.user
    guild = interaction.guild

    # Check if user is already verified
    existing = await get_user_by_discord_id(user.id)
    if existing:
        await interaction.followup.send(
            f"You are already verified as **{existing['s21_login']}**",
            ephemeral=True
        )
        return

    # Check if login is already taken by another user
    if await is_login_taken(login):
        await interaction.followup.send(
            "This School 21 login is already linked to another Discord account.",
            ephemeral=True
        )
        return

    # Check if participant exists on School 21 platform
    if not await s21_api.participant_exists(login):
        await interaction.followup.send(
            f"User **{login}** was not found on the School 21 platform. "
            "Please check your login and try again.",
            ephemeral=True
        )
        return

    # Get coalition info
    coalition_name = await s21_api.get_coalition_name(login)
    coalition_role_id = get_coalition_role_id(coalition_name)

    # Get roles to assign
    roles_to_add = []
    role_names = []

    # Add peer role
    if PEER_ROLE_ID:
        peer_role = guild.get_role(PEER_ROLE_ID)
        if peer_role:
            roles_to_add.append(peer_role)
            role_names.append(peer_role.name)

    # Add coalition role
    if coalition_role_id:
        coalition_role = guild.get_role(coalition_role_id)
        if coalition_role:
            roles_to_add.append(coalition_role)
            role_names.append(coalition_role.name)

    # Apply roles
    try:
        if roles_to_add:
            await user.add_roles(*roles_to_add, reason="School 21 verification")
    except discord.Forbidden:
        await interaction.followup.send(
            "Bot doesn't have permission to assign roles. "
            "Please contact an administrator.",
            ephemeral=True
        )
        return
    except Exception as e:
        logger.error(f"Failed to assign roles: {e}")
        await interaction.followup.send(
            "An error occurred while assigning roles. Please try again later.",
            ephemeral=True
        )
        return

    # Change nickname
    try:
        await user.edit(nick=login)
    except discord.Forbidden:
        logger.warning(f"Cannot change nickname for {user.name} - insufficient permissions")
    except Exception as e:
        logger.error(f"Failed to change nickname: {e}")

    # Save to database
    await add_verified_user(user.id, login, coalition_name)

    # Build success message
    message = f"Successfully verified as **{login}**!"
    if role_names:
        message += f"\nRoles assigned: {', '.join(role_names)}"
    if coalition_name:
        message += f"\nCoalition: {coalition_name}"

    await interaction.followup.send(message, ephemeral=True)
    logger.info(f"User {user.name} verified as {login} (coalition: {coalition_name})")


@bot.tree.command(name="whois", description="Check who a Discord user is on School 21")
@app_commands.describe(member="The Discord member to check")
async def whois(interaction: discord.Interaction, member: discord.Member):
    """Check verified info for a Discord member."""
    user_data = await get_user_by_discord_id(member.id)

    if user_data:
        await interaction.response.send_message(
            f"**{member.display_name}** is verified as **{user_data['s21_login']}**"
            + (f" (Coalition: {user_data['coalition']})" if user_data['coalition'] else ""),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"**{member.display_name}** is not verified.",
            ephemeral=True
        )


@bot.tree.command(name="myinfo", description="Show your School 21 verification info")
async def myinfo(interaction: discord.Interaction):
    """Show user's own verification info."""
    user_data = await get_user_by_discord_id(interaction.user.id)

    if user_data:
        embed = discord.Embed(
            title="Your School 21 Info",
            color=discord.Color.green()
        )
        embed.add_field(name="Login", value=user_data['s21_login'], inline=False)
        if user_data['coalition']:
            embed.add_field(name="Coalition", value=user_data['coalition'], inline=False)
        embed.add_field(
            name="Verified at",
            value=user_data['verified_at'],
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(
            "You are not verified yet. Use `/verify` to link your School 21 account.",
            ephemeral=True
        )


@bot.event
async def on_member_join(member: discord.Member):
    """Send welcome message to new members."""
    try:
        await member.send(
            f"Welcome to the School 21 Discord server!\n\n"
            f"To get access to the server, please verify your School 21 account "
            f"by using the `/verify` command in the server and entering your School 21 login."
        )
    except discord.Forbidden:
        logger.warning(f"Cannot send DM to {member.name}")
    except Exception as e:
        logger.error(f"Failed to send welcome message: {e}")


def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN is not set in .env file")
        return
    if not S21_USERNAME or not S21_PASSWORD:
        logger.error("S21_USERNAME or S21_PASSWORD is not set in .env file")
        return

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
