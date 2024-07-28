# Trading card discord bot

import datetime
import os
import random
from typing import Set, Mapping, Any, List

import discord
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

commandprefix = "!"

embed_msg_color_standard = 0x44a0ff
embed_msg_color_error = 0xff0000
embed_msg_color_success = 0x00ff00

MAX_FIELDS_PER_EMBED = 25

# How often can the user claim in seconds
timely_claim_cooldown = 20

# Timely card claim weights
timely_claim_common_weight = 300
timely_claim_rare_weight = 40
timely_claim_epic_weight = 5
timely_claim_legendary_weight = 1


# Set up the database
def get_database():
    conn_string = os.getenv('MONGO_CONNECTION_STRING')
    dbclient = None
    try:
        # This connects to the Database Server
        dbclient = MongoClient(conn_string)
    except Exception as e:
        print("Error connecting to database: ", e)
    # This creates the database
    return dbclient["trading_card_system"]


database = get_database()
if database is None:
    print("Error connecting to database")
    exit(1)
print("Connected to database")

class UserStaff:
    def __init__(self, discord_id: int, access_type: str):
        # access_type can be "owner", "admin", or "moderator"
        # owner is similar to admin, but cannot be demoted
        self.discord_id = discord_id
        self.access_type = access_type

    def todict(self) -> dict:
        variables = vars(self)
        return {key: variables[key] for key in variables}

    @staticmethod
    def fromdict(user_object: dict | Mapping[str, Any]):
        key_value_pairs = user_object.items()
        key_value_pairs = dict(key_value_pairs)
        key_value_pairs.pop("_id")
        try:
            dict_to_user = UserStaff(**key_value_pairs)
        except Exception as e:
            raise e
        return dict_to_user

    @staticmethod
    def check_access(user_id: int, access_type_needed: str) -> bool:
        # Admin > Moderator > None
        # Owners are similar to admins, but cannot be demoted
        target_staff = UserStaff.get_staff(user_id)
        if target_staff is None:
            return False
        if target_staff.access_type == "owner":
            return True
        if target_staff.access_type == "admin" and access_type_needed != "owner":
            return True
        if target_staff.access_type == "moderator" and access_type_needed == "moderator":
            return True
        return False

    @staticmethod
    def get_staff(discord_user_id: int):
        global staff_collection
        getting_staff = staff_collection.find_one({"discord_id": discord_user_id})
        if getting_staff is not None:
            return UserStaff.fromdict(getting_staff)
        else:
            return None


class TCGItem:
    def __init__(self, card_id: int, name: str, rarity: str, description: str):
        valid_rarities = ["common", "rare", "epic", "legendary"]
        if rarity not in valid_rarities:
            raise ValueError(f"Invalid rarity: {rarity}")

        self.card_id = card_id
        self.name = name
        self.rarity = rarity
        self.description = description


class Card(TCGItem):
    def __init__(self, card_id: int, name: str, card_type: str, rarity: str, description: str):
        super().__init__(card_id, name, rarity, description)
        valid_card_types = ["color", "shape", "element", "emotion", "number", "border"]
        if card_type not in valid_card_types:
            raise ValueError(f"Invalid card type: {card_type}")
        self.card_type = card_type

    def todict(self) -> dict:
        variables = vars(self)
        return {key: variables[key] for key in variables}

    @staticmethod
    def fromdict(card_object: dict | Mapping[str, Any]):
        key_value_pairs = card_object.items()
        key_value_pairs = dict(key_value_pairs)
        key_value_pairs.pop("_id")
        try:
            dict_to_card = Card(**key_value_pairs)
        except Exception as e:
            raise e
        return dict_to_card

class UniqueCard:
    def __init__(self, card_id: int, card_owner: int):
        self.card_id = card_id
        self.card_owner = card_owner

    def todict(self) -> dict:
        variables = vars(self)
        return {key: variables[key] for key in variables}

    @staticmethod
    def fromdict(unique_card_object: dict | Mapping[str, Any]):
        key_value_pairs = unique_card_object.items()
        key_value_pairs = dict(key_value_pairs)
        key_value_pairs.pop("_id")
        try:
            dict_to_unique_card = UniqueCard(**key_value_pairs)
        except Exception as e:
            raise e
        return dict_to_unique_card


class AssembledItem(TCGItem):
    def __init__(self, custom_name: str, cards: Set[Card], card_id: int, name: str, rarity: str, description: str):
        super().__init__(card_id, name, rarity, description)
        self.custom_name = custom_name
        self.cards = cards

class User:
    def __init__(self, discord_id: int, registration_date: datetime, claim_date: datetime, level: int, exp: int,
                 balance: int,
                 cards: List[Card]):
        self.discord_id = discord_id
        self.registration_date = registration_date
        self.claim_date = claim_date
        self.level = level
        self.exp = exp
        self.balance = balance
        self.cards = cards

    @classmethod
    def new_user(cls, discord_id: int):
        return cls(discord_id=discord_id, registration_date=datetime.datetime.now(), claim_date=datetime.datetime.now(),
                   level=1,
                   exp=0, balance=0, cards=[])

    def todict(self) -> dict:
        variables = vars(self)
        return {key: variables[key] for key in variables}

    def todict_user_view(self) -> dict:
        variables = vars(self)
        return {key: variables[key] for key in variables if key != "cards"}

    @staticmethod
    def fromdict(user_object: dict | Mapping[str, Any]):
        key_value_pairs = user_object.items()
        key_value_pairs = dict(key_value_pairs)
        key_value_pairs.pop("_id")
        try:
            dict_to_user = User(**key_value_pairs)
        except Exception as e:
            raise e
        return dict_to_user

    @staticmethod
    def get_user(discord_user_id: int):
        getting_user = user_collection.find_one({"discord_id": discord_user_id})
        if getting_user is not None:
            return User.fromdict(getting_user)
        else:
            return None


# User Collection stores a collection of users, their stats, and their inventories
user_collection = database["users"]

# Stores all the possible cards that could be obtained in the game
card_collection = database["cards"]

# Staff Collection stores a collection of staff members and their access levels
staff_collection = database["staff"]

# Cards that have been created and are owned by a user
cards_in_existence = database["cards_in_existence"]

# Initialize the user collection if it doesn't exist
# This is likely to be updated very frequently as new users join the game and their stats are updated
if user_collection.count_documents({}) == 0:
    user = User(discord_id=0, registration_date=datetime.datetime.now(), claim_date=datetime.datetime.now(), level=1,
                exp=0, balance=0, cards=[])
    user_collection.insert_one(user.todict())
    print("User collection initialized")
# Initialize the card collection if it doesn't exist
# This is less likely to be updated frequently as it only needs to be updated when new cards are added

if card_collection.count_documents({}) == 0:
    # Loads up CSVs, converts them into dicts, 1st row is header.
    cardid = 0
    with open("cardslist_bootstrap_files/cardslist_bootstrap_commons.csv", "r") as file:
        next(file)
        for line in file:
            card = line.split(",")
            card = Card(card_id=cardid, name=card[0], card_type=card[1], rarity="common", description=card[2])
            card_collection.insert_one(card.todict())
            cardid += 1
    with open("cardslist_bootstrap_files/cardslist_bootstrap_rares.csv", "r") as file:
        next(file)
        for line in file:
            card = line.split(",")
            card = Card(card_id=cardid, name=card[0], card_type=card[1], rarity="rare", description=card[2])
            card_collection.insert_one(card.todict())
            cardid += 1
    with open("cardslist_bootstrap_files/cardslist_bootstrap_epics.csv", "r") as file:
        next(file)
        for line in file:
            card = line.split(",")
            card = Card(card_id=cardid, name=card[0], card_type=card[1], rarity="epic", description=card[2])
            card_collection.insert_one(card.todict())
            cardid += 1
    with open("cardslist_bootstrap_files/cardslist_bootstrap_legendaries.csv", "r") as file:
        next(file)
        for line in file:
            card = line.split(",")
            card = Card(card_id=cardid, name=card[0], card_type=card[1], rarity="legendary", description=card[2])
            card_collection.insert_one(card.todict())
            cardid += 1

    print("Card collection initialized")
if staff_collection.count_documents({}) == 0:

    # The owner of the bot is xnexus1
    staff = UserStaff(discord_id=166001619735937024, access_type="owner")
    staff_collection.insert_one(staff.todict())
    print("Staff collection initialized")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(commandprefix):
        command = message.content.split(" ")[0][1:]
        args = message.content.split(" ")[1:]
        await message.delete()
        if command == "pingme":
            embedmsg = discord.Embed(title="Pong!", description="You have been pinged", color=embed_msg_color_standard)
            await message.channel.send(embed=embedmsg)
            return
        if command == "help":
            await message.channel.send(embed=cmdhelp(args[0] if len(args) > 0 else None))
            return
        if command == "checkperms":
            if len(args) == 0 or not UserStaff.check_access(message.author.id, "moderator"):
                # If moderator, 1st arg can be used to check perms of another user, otherwise, it will check the perms of the user
                try:
                    embedmsg = discord.Embed(title="User Permissions",
                                         description=f'Your permissions: {UserStaff.get_staff(message.author.id).access_type}',
                                         color=embed_msg_color_standard)
                    await message.channel.send(embed=embedmsg)
                except:
                    embedmsg = discord.Embed(title="Error", description="You do not have permission to use this command",
                                         color=embed_msg_color_error)
                    await message.channel.send(embed=embedmsg)
                return
            # reformat the 1st arg to be an integer
            targetid = int(args[0].replace("<@", "").replace(">", ""))
            targetperms = UserStaff.get_staff(targetid)
            embedmsg = discord.Embed(title="User Permissions",
                                     description=f'User permissions of {targetid}: {targetperms}',
                                     color=embed_msg_color_standard)
            await message.channel.send(embed=embedmsg)
            return
        if command == "register":
            getting_user = User.get_user(message.author.id)
            if getting_user is not None:
                embedmsg = discord.Embed(title="Error", description="You are already registered",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            getting_user = User.new_user(message.author.id)
            user_collection.insert_one(getting_user.todict())
            embedmsg = discord.Embed(title="Success", description="You have been registered",
                                     color=embed_msg_color_success)
            await message.channel.send(embed=embedmsg)
        if command == "inventory":
            getting_user = User.get_user(message.author.id)
            if getting_user is None:
                embedmsg = discord.Embed(title="Error",
                                         description="You are not registered.\nUse !register to register",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            embedmsg = discord.Embed(title=f"{message.author.name}'s Inventory", description="Your inventory",
                                     color=embed_msg_color_standard)
            for (i, getting_card) in enumerate(getting_user.cards):
                if len(embedmsg.fields) >= MAX_FIELDS_PER_EMBED:
                    await message.channel.send(embed=embedmsg)
                    embedmsg = discord.Embed(title="Inventory", description="Your inventory",
                                             color=embed_msg_color_standard)
                embedmsg.add_field(name=f"{i + 1}.",
                                   value=f"Name: {getting_card['name']}\nRarity: {getting_card['rarity']}\nDescription: {getting_card['description']}",
                                   inline=True)
            await message.channel.send(embed=embedmsg)
            return
        if command == "claim":
            getting_user = User.get_user(message.author.id)
            if getting_user is None:
                embedmsg = discord.Embed(title="Error",
                                         description="You are not registered.\nUse !register to register",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            # Check if the user has already claimed their daily card
            difference_between_now_and_claim_date_in_seconds = (
                    datetime.datetime.now() - pd.to_datetime(getting_user.claim_date).to_pydatetime()).total_seconds()
            time_to_wait = timely_claim_cooldown - difference_between_now_and_claim_date_in_seconds
            if time_to_wait > 0:
                embedmsg = discord.Embed(title="Error",
                                         description=f"You have already claimed your timely card.\n You must wait for {int(time_to_wait)} seconds before you can claim again.",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            # Claim the card
            # Generate a random number between 0 and the sum of all the weights
            # If the number is between 0 and the common weight, the user gets a common card
            # If the number is between the common weight and the sum of the common and rare weights, the user gets a rare card
            # If the number is between the sum of the common and rare weights and the sum of the common, rare, and epic weights, the user gets an epic card
            # If the number is between the sum of the common, rare, and epic weights and the sum of the common, rare, epic, and legendary weights, the user gets a legendary card
            card_rarity = weightedpick(["common", "rare", "epic", "legendary"],
                                       [timely_claim_common_weight, timely_claim_rare_weight, timely_claim_epic_weight,
                                        timely_claim_legendary_weight])
            allcards = card_collection.find(({"rarity": card_rarity}))
            cardslist = []
            while allcards.alive:
                getting_card = allcards.next()
                cardslist.append(getting_card if getting_card is not None else [])
            getting_card = random.choice(cardslist)
            user_collection.update_one({"discord_id": message.author.id}, {"$push": {"cards": getting_card}})
            user_collection.update_one({"discord_id": message.author.id},
                                       {"$set": {"claim_date": datetime.datetime.now()}})
            embedmsg = discord.Embed(title="Success", description=f"Card claimed: {getting_card['name']}",
                                     color=embed_msg_color_success)
            embedmsg.add_field(name="Rarity", value=getting_card['rarity'], inline=True)
            await message.channel.send(embed=embedmsg)
            return

        if command == "debug":
            if not UserStaff.check_access(message.author.id, "admin"):
                embedmsg = discord.Embed(title="Error", description="You do not have permission to use this command",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            # subcommand is either args[0] or None
            subcommand = None
            if len(args) > 0:
                subcommand = args[0]
            if subcommand == "args":
                embedmsg = discord.Embed(title="Debug Information", description="Arguments:",
                                         color=embed_msg_color_standard)
                for (i, arg) in enumerate(args):
                    embedmsg.add_field(name=f"Argument {i}", value=arg, inline=False)
                await message.channel.send(embed=embedmsg)
                return
            if subcommand == "cardslist":
                cards = card_collection.find({})
                embedmsg = discord.Embed(title="Card List", description="List of all cards in the game",
                                         color=embed_msg_color_standard)
                for getting_card in cards:
                    if len(embedmsg.fields) >= MAX_FIELDS_PER_EMBED:
                        await message.channel.send(embed=embedmsg)
                        embedmsg = discord.Embed(title="Card List", description="List of all cards in the game",
                                                 color=embed_msg_color_standard)
                    embedmsg.add_field(name=f"Card ID: {getting_card['card_id']}",
                                       value=f"Name: {getting_card['name']}\nRarity: {getting_card['rarity']}\nDescription: {getting_card['description']}",
                                       inline=False)

                await message.channel.send(embed=embedmsg)
                return
            if subcommand == "userslist":
                users = user_collection.find({})
                embedmsg = discord.Embed(title="User List", description="List of all users in the game",
                                         color=embed_msg_color_standard)
                for getting_user in users:
                    embedmsg.add_field(name=f"Discord ID: {getting_user['discord_id']}",
                                       value=f"Registration Date: {getting_user['registration_date']}\nLevel: {getting_user['level']}\nExp: {getting_user['exp']}\nBalance: {getting_user['balance']}",
                                       inline=False)
                await message.channel.send(embed=embedmsg)
                return
            if subcommand == "stafflist":
                getting_staff = staff_collection.find({})
                embedmsg = discord.Embed(title="Staff List", description="List of all staff members",
                                         color=embed_msg_color_standard)
                for getting_user in getting_staff:
                    embedmsg.add_field(name=f"Discord ID: {getting_user['discord_id']}",
                                       value=f"Access Type: {getting_user['access_type']}", inline=False)
                await message.channel.send(embed=embedmsg)
                return
            if subcommand == "nuketrades":
                active_trades = database["active_trades"]
                # Get "Trading" category
                trade_category = None
                for category in message.guild.categories:
                    if category.name == "Trading":
                        trade_category = category
                        break
                if trade_category is None:
                    await message.channel.send("No active trades to delete")
                    return
                # Delete all channels in the "Trading" category
                for channel in trade_category.channels:
                    await channel.delete()
                active_trades.delete_many({})
                await message.channel.send("All active trades have been deleted")
                return
        if command == "trade":
            # Start a trade with another user
            # Try to get the user id from the first argument as a mention
            target_id = int(args[0].replace("<@", "").replace(">", ""))
            # Is the initiator of the trade registered?
            initiator = User.get_user(message.author.id)
            if initiator is None:
                embedmsg = discord.Embed(title="Error", description="You are not registered",
                                     color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            # Is the target of the trade registered?
            target = User.get_user(target_id)
            if target is None:
                embedmsg = discord.Embed(title="Error", description="The target user is not registered",
                                     color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            # Is the initiator of the trade trying to trade with themselves?
            if target_id == message.author.id:
                embedmsg = discord.Embed(title="Error", description="You cannot trade with yourself",
                                     color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            # Create a new channel, then put the initiator and target in the channel.
            # The channel will be used to conduct the trade.

            # If the trading category doesn't exist, create it
            trade_category = None
            for category in message.guild.categories:
                if category.name == "Trading":
                    trade_category = category
                    break
            if trade_category is None:
                trade_category = await message.guild.create_category("Trading")

            # Create a new channel, then put the initiator and target in the channel.
            # The Channel is in the Trading Category
            random_channel_identifier = random.randint(100000, 999999)
            trade_channel = await message.guild.create_text_channel(f"trade-{random_channel_identifier}", category=trade_category)
            active_trades = database["active_trades"]

            target_member = await client.get_guild(message.guild.id).fetch_member(target_id)
            await trade_channel.set_permissions(message.author, read_messages=True, send_messages=True)
            await trade_channel.set_permissions(target_member, read_messages=True, send_messages=True)
            await trade_channel.edit(topic=f"Trade between: {message.author.name} and {target_member.name}\ntrade id: {random_channel_identifier}")
            embeddesc = ("A trading session has been started. Use this channel to conduct the trade.\n"
                         "Do !inv to check your inventory, and !offer <card id> to offer a card.\n"
                         "Do !remove <card id> to remove a card from the trade.\n"
                         "Both users must !accept to complete the trade.\n"
                         "To cancel the trade, one user can do !cancel.")
            embedmsg = discord.Embed(title="Trade Session", description=embeddesc, color=embed_msg_color_standard)
            await trade_channel.send(embed=embedmsg)
            # Displays information regarding items being traded.
            monitor_msg = await trade_channel.send("-")
            monitor_msg = monitor_msg.id
            active_trades.insert_one(
                {"trade_id": random_channel_identifier, "channel_id": trade_channel.id, "monitor-id": monitor_msg,
                 "user1": message.author.id, "user2": target_id, "user1-items": [], "user2-items": [], "user1-accept": False, "user2-accept": False})
            await update_display_trade_entries(random_channel_identifier)


        if command == "inv" or command == "offer" or command == "remove" or command == "accept" or command == "cancel":
            # Is the user in the trading channel?
            if message.channel.category.name != "Trading":
                return
            if command == "inv":
                # Display the user's inventory
                getting_user = User.get_user(message.author.id)
                embedmsg = discord.Embed(title=f"{message.author.name}'s Inventory", description="Your inventory",
                                         color=embed_msg_color_standard)
                for (i, getting_card) in enumerate(getting_user.cards):
                    embedmsg.add_field(name=f"{i + 1}.",
                                     value=f"Name: {getting_card['name']}\nRarity: {getting_card['rarity']}\nDescription: {getting_card['description']}",
                                     inline=True)
                await message.channel.send(embed=embedmsg)
                return
            if command == "offer":
                # Offer a card
                # Is the user offering a card?
                if len(args) == 0:
                    return
                # Is the card id a valid integer?
                try:
                    card_id = int(args[0])
                except:
                    return
                # Does the user have the card?
                getting_user = User.get_user(message.author.id)
                if getting_user is None:
                    return
                if card_id < 1 or card_id > len(getting_user.cards):
                    return
                # Add the card to the trade
                active_trades = database["active_trades"]
                trade_id = active_trades.find_one({"channel_id": message.channel.id})["trade_id"]
                cardslist = active_trades.find_one({"trade_id": trade_id})[f"user{1 if message.author.id == active_trades.find_one({'trade_id': trade_id})['user1'] else 2}-items"]
                cardslist.append(getting_user.cards[card_id - 1])
                active_trades.update_one({"trade_id": trade_id}, {"$set": {f"user{1 if message.author.id == active_trades.find_one({'trade_id': trade_id})['user1'] else 2}-items": cardslist}})
                await update_display_trade_entries(trade_id)
                # Both users should have their trade consent set to false
                active_trades.update_one({"trade_id": trade_id}, {"$set": {"user1-accept": False}})
                active_trades.update_one({"trade_id": trade_id}, {"$set": {"user2-accept": False}})
                return
            if command == "remove":
                # Remove a card from the trade
                # Is the user removing a card?
                if len(args) == 0:
                    return
                # Is the card id a valid integer?
                try:
                    card_id = int(args[0])
                except:
                    return
                # Is the card id a valid integer?
                try:
                    card_id = int(args[0])
                except:
                    return
                # Does the user have the card?
                getting_user = User.get_user(message.author.id)
                if getting_user is None:
                    return
                if card_id < 1 or card_id > len(getting_user.cards):
                    return
                # Remove the card from the trade
                active_trades = database["active_trades"]
                trade_id = active_trades.find_one({"channel_id": message.channel.id})["trade_id"]
                cardslist = active_trades.find_one({"trade_id": trade_id})[f"user{1 if message.author.id == active_trades.find_one({'trade_id': trade_id})['user1'] else 2}-items"]
                cardslist.pop(card_id - 1)
                active_trades.update_one({"trade_id": trade_id}, {"$set": {f"user{1 if message.author.id == active_trades.find_one({'trade_id': trade_id})['user1'] else 2}-items": cardslist}})
                await update_display_trade_entries(trade_id)
                # Both users should have their trade consent set to false
                active_trades.update_one({"trade_id": trade_id}, {"$set": {"user1-accept": False}})
                active_trades.update_one({"trade_id": trade_id}, {"$set": {"user2-accept": False}})
                return
            if command == "accept":
                # Accept the trade
                active_trades = database["active_trades"]
                trade_id = active_trades.find_one({"channel_id": message.channel.id})["trade_id"]
                if message.author.id == active_trades.find_one({"trade_id": trade_id})["user1"]:
                    active_trades.update_one({"trade_id": trade_id}, {"$set": {"user1-accept": True}})
                if message.author.id == active_trades.find_one({"trade_id": trade_id})["user2"]:
                    active_trades.update_one({"trade_id": trade_id}, {"$set": {"user2-accept": True}})
                if active_trades.find_one({"trade_id": trade_id})["user1-accept"] and active_trades.find_one({"trade_id": trade_id})["user2-accept"]:
                    # Both users have accepted the trade
                    # Give the cards to the other user
                    user1 = User.get_user(active_trades.find_one({"trade_id": trade_id})["user1"])
                    user2 = User.get_user(active_trades.find_one({"trade_id": trade_id})["user2"])
                    user1_cards = active_trades.find_one({"trade_id": trade_id})["user1-items"]
                    user2_cards = active_trades.find_one({"trade_id": trade_id})["user2-items"]
                    user_collection.update_one({"discord_id": user1.discord_id}, {"$set": {"cards": user1_cards}})
                    user_collection.update_one({"discord_id": user2.discord_id}, {"$set": {"cards": user2_cards}})
                    # Delete the trade
                    active_trades.delete_one({"trade_id": trade_id})
                    await message.channel.delete()
                return
            if command == "cancel":
                # Cancel the trade
                active_trades = database["active_trades"]
                trade_id = active_trades.find_one({"channel_id": message.channel.id})["trade_id"]
                active_trades.delete_one({"trade_id": trade_id})
                await message.channel.delete()
                return














            # No subcommand was given, whoops
            embedmsg = discord.Embed(title="Error", description="Invalid subcommand", color=embed_msg_color_error)
            await message.channel.send(embed=embedmsg)
            return

async def update_display_trade_entries(trade_id: int):
    active_trades = database["active_trades"]
    trade_channel = discord.utils.get(client.get_all_channels(), id=active_trades.find_one({"trade_id": trade_id})["channel_id"])

    embedmsg = discord.Embed(title="Items offered", color=embed_msg_color_standard)
    # User 1 items
    embedfield_name = f"{discord.utils.get(trade_channel.guild.members, id=active_trades.find_one('user1'))}'s items"
    item_list = []
    for item in active_trades.find_one({"trade_id": trade_id})["user1-items"]:
        item_list.append(item)
    embedmsg.add_field(name=embedfield_name, value="\n".join(item_list), inline=False)
    # User 2 items
    embedfield_name = f"{discord.utils.get(trade_channel.guild.members, id=active_trades.find_one('user2'))}'s items"
    item_list = []
    for item in active_trades.find_one({"trade_id": trade_id})["user2-items"]:
        item_list.append(item)
    embedmsg.add_field(name=embedfield_name, value="\n".join(item_list), inline=False)
    # Get last message of the bot in the channel
    await trade_channel.send(embed=embedmsg)



def weightedpick(options, weights):
    total = sum(weights)
    r = random.uniform(0, total)
    for (i, w) in enumerate(weights):
        r -= w
        if r < 0:
            return options[i]
    return options[-1]


def cmdhelp(category):
    if category == "debug":
        embedmsg = discord.Embed(title="Debug Command Reference", description="List of commands for the debug command",
                                 color=embed_msg_color_standard)
        embedmsg.add_field(name="!debug args", value="Displays the arguments given to the debug command", inline=True)
        embedmsg.add_field(name="!debug cardslist", value="Displays a list of all cards in the game", inline=True)
        embedmsg.add_field(name="!debug userslist", value="Displays a list of all users in the game", inline=True)
        embedmsg.add_field(name="!debug stafflist", value="Displays a list of all staff members", inline=True)
        return embedmsg

    if category is not None:
        embedmsg = discord.Embed(title="Error", description="Invalid category", color=embed_msg_color_error)
        return embedmsg

    embedmsg = discord.Embed(title="Command Reference", description="List of commands for the trading card bot",
                             color=embed_msg_color_standard)
    embedmsg.add_field(name="!pingme", value="Pings the user", inline=True)
    embedmsg.add_field(name="!help", value="Displays this message", inline=True)
    embedmsg.add_field(name="!register", value="Registers the user into the game", inline=True)
    embedmsg.add_field(name="!checkperms", value="Checks the permissions of the user", inline=True)
    embedmsg.add_field(name="!inventory", value="Displays the user's inventory", inline=True)
    embedmsg.add_field(name="!claim", value="Claims a card", inline=True)
    embedmsg.add_field(name="!debug", value="Debug commands, for admin use only", inline=True)

    return embedmsg


@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')



client.run(token)
