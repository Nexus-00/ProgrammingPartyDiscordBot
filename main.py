# Trading card discord bot

import datetime
import os
import random
from typing import Set, Mapping, Any

import discord
import pandas as pd
from discord import HTTPException
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

# Don't change this.
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

    @classmethod
    def dict_item_type_equal(self, item_dict: dict) -> bool:
        raise NotImplementedError("This method must be implemented in a subclass")


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

    @classmethod
    def dict_item_type_equal(cls, item_dict: dict) -> bool:
        try:
            item_object = cls.fromdict(item_dict)
        except Exception as e:
            raise e
        return isinstance(item_object, cls)


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




class CardPack(TCGItem):
    def __init__(self, pack_id: int, name: str, rarity: str, description: str, cards: list[Card]):
        super().__init__(pack_id, name, rarity, description)
        self.cards = cards

    def todict(self) -> dict:
        variables = vars(self)
        return {key: variables[key] for key in variables}

    @staticmethod
    def fromdict(cardpack_object: dict | Mapping[str, Any]):
        key_value_pairs = cardpack_object.items()
        key_value_pairs = dict(key_value_pairs)
        key_value_pairs.pop("_id")
        try:
            dict_to_cardpack = CardPack(**key_value_pairs)
        except Exception as e:
            raise e
        return dict_to_cardpack

    @classmethod
    def assemble_pack(cls, type: str):
        # Type can be "common", "rare", "epic", "legendary", "pay2win"
        if type == "common":
            # Generate 5 random cards using weighted chances
            cardsdicts = []
            for i in range(5):
                card_rarity = random.choices(population=["common", "rare", "epic", "legendary"],
                                             weights=[timely_claim_common_weight, timely_claim_rare_weight,
                                                      timely_claim_epic_weight,
                                                      timely_claim_legendary_weight], k=1)[0]
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts.append(getting_card)
            return cls(pack_id=0, name="Common Card Pack", rarity="common", description="A pack of 5 cards",
                       cards=cardsdicts)
        if type == "rare":
            # Generate 5 random cards using weighted chances, with a guaranteed rare card or better
            cardsdicts = []
            for i in range(5):
                card_rarity = random.choices(population=["common", "rare", "epic", "legendary"],
                                             weights=[timely_claim_common_weight, timely_claim_rare_weight,
                                                      timely_claim_epic_weight,
                                                      timely_claim_legendary_weight], k=1)[0]
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts.append(getting_card)
            # Check if the cards are only commons
            if all(card.rarity == "common" for card in cardsdicts):
                # Replace a random common card with a rare card
                card_rarity = "rare"
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts[random.randint(0, 4)] = getting_card
            return cls(pack_id=1, name="Rare Card Pack", rarity="rare",
                       description="A pack of 5 cards, with a guaranteed rare card", cards=cardsdicts)
        if type == "epic":
            # Generate 5 random cards using weighted chances, with a guaranteed epic card or better
            cardsdicts = []
            for i in range(5):
                card_rarity = random.choices(population=["common", "rare", "epic", "legendary"],
                                             weights=[timely_claim_common_weight, timely_claim_rare_weight,
                                                      timely_claim_epic_weight,
                                                      timely_claim_legendary_weight], k=1)[0]
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts.append(getting_card)
            # Check if the cards are only commons and rares
            if all(card.rarity in ["common", "rare"] for card in cardsdicts):
                # Replace a random common or rare card with an epic card
                card_rarity = "epic"
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts[random.randint(0, 4)] = getting_card
            return cls(pack_id=2, name="Epic Card Pack", rarity="epic",
                       description="A pack of 5 cards, with a guaranteed epic card", cards=cardsdicts)
        if type == "legendary":
            # Generate 5 random cards using weighted chances, with a guaranteed legendary card
            cardsdicts = []
            for i in range(5):
                card_rarity = random.choices(population=["common", "rare", "epic", "legendary"],
                                             weights=[timely_claim_common_weight, timely_claim_rare_weight,
                                                      timely_claim_epic_weight,
                                                      timely_claim_legendary_weight], k=1)[0]
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts.append(getting_card)
            # Check if the cards are only commons, rares, or epics
            if all(card.rarity in ["common", "rare", "epic"] for card in cardsdicts):
                # Replace a random common, rare, or epic card with a legendary card
                card_rarity = "legendary"
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts[random.randint(0, 4)] = getting_card
            return cls(pack_id=3, name="Legendary Card Pack", rarity="legendary",
                       description="A pack of 5 cards, with a guaranteed legendary card", cards=cardsdicts)
        if type == "pay2win":
            # Generate 5 random cards using weighted chances, with only epics or legendaries or both
            cardsdicts = []
            for i in range(5):
                card_rarity = random.choices(population=["epic", "legendary"],
                                             weights=[timely_claim_epic_weight, timely_claim_legendary_weight], k=1)[0]
                allcards = card_collection.find(({"rarity": card_rarity}))
                cardslist = []
                while allcards.alive:
                    getting_card = allcards.next()
                    cardslist.append(getting_card if getting_card is not None else [])
                getting_card = random.choice(cardslist)
                cardsdicts.append(Card.fromdict(getting_card))
            return cls(pack_id=4, name="Pay2Win Card Pack", rarity="legendary",
                       description="A pack of 5 cards, with only epic or legendary cards", cards=cardsdicts)


class User:
    def __init__(self, discord_id: int, registration_date: datetime, claim_date: datetime, level: int, exp: int,
                 balance: int, inventory: list[dict]):
        self.discord_id = discord_id
        self.registration_date = registration_date
        self.claim_date = claim_date
        self.level = level
        self.exp = exp
        self.balance = balance
        self.inventory = inventory

    @classmethod
    def new_user(cls, discord_id: int):
        return cls(discord_id=discord_id,
                   registration_date=datetime.datetime.now() - datetime.timedelta(seconds=timely_claim_cooldown),
                   claim_date=datetime.datetime.now(),
                   level=1,
                   exp=0, balance=50, inventory=[])

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
generated_cards_collection = database["generated_cards"]

# Initialize the user collection if it doesn't exist
# This is likely to be updated very frequently as new users join the game and their stats are updated
if user_collection.count_documents({}) == 0:
    user = User.new_user(0)
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
                except ValueError:
                    embedmsg = discord.Embed(title="Error",
                                             description="You do not have permission to use this command",
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

            # Iterate over the user's inventory of items, such as card packs
            for item in getting_user.inventory:
                if True:
                    # If the item is a card pack, display the card pack details
                    embedmsg.add_field(name=f"{item.name}",
                                       value=f"Rarity: {item.rarity}\nDescription: {item.description}",
                                       inline=True)
                # Add more types of items here later.

            await message.channel.send(embed=embedmsg)

            embedmsg = discord.Embed(title=f"{message.author.name}'s Cards", description="Your inventory",
                                     color=embed_msg_color_standard)

            cards_in_inventory = {}
            card_count = {}

            # Get all cards owned by the user
            owned_cards = generated_cards_collection.find({"card_owner": message.author.id})

            # Iterate over the owned cards
            for owned_card in owned_cards:
                # Get the card details from the card collection
                card_details = card_collection.find_one({"card_id": owned_card["card_id"]})

                # Convert the card details to a Card object
                this_card = Card.fromdict(card_details)

                # If the card is not in the inventory, add it and initialize the count to 1
                if this_card.card_id not in cards_in_inventory:
                    cards_in_inventory[this_card.card_id] = this_card
                    card_count[this_card.card_id] = 1
                else:
                    # If the card is already in the inventory, increment the count
                    card_count[this_card.card_id] += 1

            # Get player's balance
            player_balance = user_collection.find_one({"discord_id": message.author.id})["balance"]
            embedmsg.add_field(name="Balance", value=f"${player_balance}", inline=False)

            # Add the cards to the embed message
            for card_id, this_card in cards_in_inventory.items():
                embedmsg.add_field(name=f"{this_card.name} x{card_count[card_id]}",
                                   value=f"Rarity: {this_card.rarity}\nDescription: {this_card.description}",
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
            card_rarity = random.choices(population=["common", "rare", "epic", "legendary"],
                                         weights=[timely_claim_common_weight, timely_claim_rare_weight,
                                                  timely_claim_epic_weight,
                                                  timely_claim_legendary_weight], k=1)[0]
            allcards = card_collection.find(({"rarity": card_rarity}))
            cardslist = []
            while allcards.alive:
                getting_card = allcards.next()
                cardslist.append(getting_card if getting_card is not None else [])
            getting_card = random.choice(cardslist)
            generated_cards_collection.insert_one(
                UniqueCard(card_id=getting_card['card_id'], card_owner=message.author.id).todict())
            user_collection.update_one({"discord_id": message.author.id},
                                       {"$set": {"claim_date": datetime.datetime.now()}})
            embedmsg = discord.Embed(title="Success", description=f"Card claimed: {getting_card['name']}",
                                     color=embed_msg_color_success)
            embedmsg.add_field(name="Rarity", value=getting_card['rarity'], inline=True)
            await message.channel.send(embed=embedmsg)
            return
        if command == "buy":
            # subcommand is either args[0] or None
            # check if the user is registered
            getting_user = User.get_user(message.author.id)
            if getting_user is None:
                embedmsg = discord.Embed(title="Error", description="You are not registered",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return

            subcommand = None
            player_balance = getting_user.balance

            if len(args) > 0:
                subcommand = args[0]
            if subcommand == "cardpack":
                subsubcommand = None
                if len(args) > 1:
                    subsubcommand = args[1]
                if subsubcommand == "common":
                    # Buy a common card pack, contains 5 random card pulls
                    if player_balance < 5:
                        embedmsg = discord.Embed(title="Error", description="You do not have enough money",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    # Deduct the cost of the card pack from the player's balance
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"balance": player_balance - 5}})
                    # Generate the card pack
                    card_pack = CardPack.assemble_pack("common")
                    # Add the card pack to the player's inventory
                    getting_user.inventory.append(card_pack.todict())
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"inventory": getting_user.inventory}})
                    embedmsg = discord.Embed(title="Success", description="Card pack purchased",
                                             color=embed_msg_color_success)
                    await message.channel.send(embed=embedmsg)
                    return

                if subsubcommand == "rare":
                    # Buy a rare card pack, contains 5 random card pulls, with a guaranteed rare card
                    if player_balance < 10:
                        embedmsg = discord.Embed(title="Error", description="You do not have enough money",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    # Deduct the cost of the card pack from the player's balance
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"balance": player_balance - 10}})
                    # Generate the card pack
                    card_pack = CardPack.assemble_pack("rare")
                    # Add the card pack to the player's inventory
                    getting_user.inventory.append(card_pack)
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"inventory": getting_user.inventory}})
                    embedmsg = discord.Embed(title="Success", description="Card pack purchased",
                                             color=embed_msg_color_success)
                    await message.channel.send(embed=embedmsg)
                    return
                if subsubcommand == "epic":
                    # Buy an epic card pack, contains 5 random card pulls, with a guaranteed epic card
                    if player_balance < 20:
                        embedmsg = discord.Embed(title="Error", description="You do not have enough money",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    # Deduct the cost of the card pack from the player's balance
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"balance": player_balance - 20}})
                    # Generate the card pack
                    card_pack = CardPack.assemble_pack("epic")
                    # Add the card pack to the player's inventory
                    getting_user.inventory.append(card_pack)
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"inventory": getting_user.inventory}})
                    embedmsg = discord.Embed(title="Success", description="Card pack purchased",
                                             color=embed_msg_color_success)
                    await message.channel.send(embed=embedmsg)
                    return
                if subsubcommand == "legendary":
                    # Buy a legendary card pack, contains 5 random card pulls, with a guaranteed legendary card
                    if player_balance < 50:
                        embedmsg = discord.Embed(title="Error", description="You do not have enough money",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    # Deduct the cost of the card pack from the player's balance
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"balance": player_balance - 50}})
                    # Generate the card pack
                    card_pack = CardPack.assemble_pack("legendary")
                    # Add the card pack to the player's inventory
                    getting_user.inventory.append(card_pack)
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"inventory": getting_user.inventory}})
                    embedmsg = discord.Embed(title="Success", description="Card pack purchased",
                                             color=embed_msg_color_success)
                    await message.channel.send(embed=embedmsg)
                    return
                if subsubcommand == "pay2win":
                    # Buy a pay2win card pack, contains 5 cards of either epics or legendary cards
                    if player_balance < 100:
                        embedmsg = discord.Embed(title="Error", description="You do not have enough money",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    # Deduct the cost of the card pack from the player's balance
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"balance": player_balance - 100}})
                    # Generate the card pack
                    card_pack = CardPack.assemble_pack("pay2win")
                    # Add the card pack to the player's inventory
                    getting_user.inventory.append(card_pack)
                    user_collection.update_one({"discord_id": message.author.id},
                                               {"$set": {"inventory": getting_user.inventory}})
                    embedmsg = discord.Embed(title="Success", description="Card pack purchased",
                                             color=embed_msg_color_success)
                    await message.channel.send(embed=embedmsg)
                    return
                embedmsg = discord.Embed(title="Error", description="Invalid subcommand",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            if subcommand is None:
                # Display the shop
                embedmsg = discord.Embed(title="Shop", description="Welcome to the shop",
                                         color=embed_msg_color_standard)
                embedmsg.add_field(name="Card Packs (cardpack)", value="Buy card packs to get random cards",
                                   inline=False)
                embedmsg.add_field(name="Common Card Pack", value="$5", inline=True)
                embedmsg.add_field(name="Rare Card Pack", value="$10", inline=True)
                embedmsg.add_field(name="Epic Card Pack", value="$20", inline=True)
                embedmsg.add_field(name="Legendary Card Pack", value="$50", inline=True)
                embedmsg.add_field(name="Pay2Win Card Pack", value="$100", inline=True)
                await message.channel.send(embed=embedmsg)
                return
        if command == "use":
            # Use an item in the inventory. For instance, a card pack
            # subcommand is either args[0] or None
            if len(args) == 0:
                embedmsg = discord.Embed(title="Error", description="Invalid arguments", color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            subcommand = args[0]
            getting_user = User.get_user(message.author.id)
            if getting_user is None:
                embedmsg = discord.Embed(title="Error", description="You are not registered",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return
            pass

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
            if subcommand == "givemoney":
                if len(args) < 3:
                    await message.channel.send("Invalid arguments")
                    return
                try:
                    target_id = int(args[1].replace("<@", "").replace(">", ""))
                    amount = int(args[2])
                except ValueError:
                    await message.channel.send("Invalid arguments")
                    return
                # If amount is negative, remove money from the user
                if amount < 0:
                    user_collection.update_one({"discord_id": target_id},
                                               {"$inc": {"balance": amount}})
                    await message.channel.send(f"${-amount} has been removed from <@{target_id}>")
                    return
                user_collection.update_one({"discord_id": target_id}, {"$inc": {"balance": amount}})
                await message.channel.send(f"${amount} has been given to <@{target_id}>")
                return
        if command == "trade":
            # Start a trade with another user
            # Try to get the user id from the first argument as a mention
            try:
                target_id = int(args[0].replace("<@", "").replace(">", ""))
            except ValueError:
                embedmsg = discord.Embed(title="Error", description="Invalid user id",
                                         color=embed_msg_color_error)
                await message.channel.send(embed=embedmsg)
                return

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
            random_channel_identifier = random.randint(10000000, 99999999)
            overwrites_trade_permissions = {
                message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                message.guild.me: discord.PermissionOverwrite(read_messages=True),
                await message.guild.fetch_member(message.author.id): discord.PermissionOverwrite(read_messages=True)
            }

            trade_channel = await message.guild.create_text_channel(f"trade-{random_channel_identifier}",
                                                                    category=trade_category,
                                                                    overwrites=overwrites_trade_permissions)
            active_trades = database["active_trades"]

            target_member = await client.get_guild(message.guild.id).fetch_member(target_id)
            await trade_channel.set_permissions(message.author, read_messages=True, send_messages=True)
            await trade_channel.set_permissions(target_member, read_messages=True, send_messages=True)
            await trade_channel.edit(
                topic=f"Trade between: {message.author.name} and {target_member.name}\ntrade id: {random_channel_identifier}")
            embeddesc = ("A trading session has been started. Use this channel to conduct the trade.\n"
                         "Do !inv to check your inventory, and !offer <card name> to offer a card.\n"
                         "When offering a card, do note that it is case sensitive. \n"
                         "Do !remove <card id> to remove a card from the trade.\n"
                         "Both users must !accept to complete the trade.\n"
                         "To cancel the trade, one user can do !cancel.")
            embedmsg = discord.Embed(title="Trade Session", description=embeddesc, color=embed_msg_color_standard)
            await trade_channel.send(embed=embedmsg)
            # Displays information regarding items being traded.
            monitor_msg = await trade_channel.send(f"Trade is starting! <@{message.author.id}> and <@{target_id}>")
            monitor_msg = monitor_msg.id
            # active_trades.insert_one(
            #    {"trade_id": random_channel_identifier, "channel_id": trade_channel.id, "monitor-id": monitor_msg,
            #     "user1": message.author.id, "user2": target_id, "user1-items": [], "user2-items": [],
            #     "user1-accept": False, "user2-accept": False})
            active_trades.insert_one(
                {"trade_id": random_channel_identifier, "channel_id": trade_channel.id, "monitor-id": monitor_msg,
                 "user_data": {
                     f"{message.author.id}": {"items": [], "accept": False, "balance": 0},
                     f"{target_id}": {"items": [], "accept": False, "balance": 0}
                 }})
            await update_display_trade_entries(random_channel_identifier)

        if command == "inv" or command == "offer" or command == "remove" or command == "accept" or command == "cancel":
            # Is the user in the trading channel?
            if message.channel.category.name != "Trading":
                return

            # Get the trade id
            active_trades = database["active_trades"]
            trade_id = active_trades.find_one({"channel_id": message.channel.id})["trade_id"]

            if command == "inv":
                # Display the user's inventory
                embedmsg = discord.Embed(title=f"{message.author.name}'s Inventory", description="Your inventory",
                                         color=embed_msg_color_standard)

                cards_in_inventory = {}
                card_count = {}

                # Get all cards owned by the user
                owned_cards = generated_cards_collection.find({"card_owner": message.author.id})

                # Iterate over the owned cards
                for owned_card in owned_cards:
                    # Get the card details from the card collection
                    card_details = card_collection.find_one({"card_id": owned_card["card_id"]})

                    # Convert the card details to a Card object
                    this_card = Card.fromdict(card_details)

                    # If the card is not in the inventory, add it and initialize the count to 1
                    if this_card.card_id not in cards_in_inventory:
                        cards_in_inventory[this_card.card_id] = this_card
                        card_count[this_card.card_id] = 1
                    else:
                        # If the card is already in the inventory, increment the count
                        card_count[this_card.card_id] += 1

                # Get player's balance
                player_balance = user_collection.find_one({"discord_id": message.author.id})["balance"]
                embedmsg.add_field(name="Balance", value=f"${player_balance}", inline=False)

                # Add the cards to the embed message
                for card_id, this_card in cards_in_inventory.items():
                    embedmsg.add_field(name=f"{this_card.name} x{card_count[card_id]}", value=f"{this_card.rarity}",
                                       inline=True)

                await message.channel.send(embed=embedmsg)
                return
            if command == "offer":
                # Allow the user to offer a card by name or money.

                # Check args if the first symbol is "$"
                if args[0][0] == "$":
                    player_balance = user_collection.find_one({"discord_id": message.author.id})["balance"]
                    currently_offered_balance = \
                    active_trades.find_one({"trade_id": trade_id})["user_data"][f"{message.author.id}"]["balance"]
                    # Currently offered balance cannot be greater than the player's balance

                    try:
                        amount = int(args[0][1:])
                    except ValueError:
                        embedmsg = discord.Embed(title="Error", description="Invalid amount",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    if amount > player_balance:
                        embedmsg = discord.Embed(title="Error", description="You do not have enough balance",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    if amount + currently_offered_balance > player_balance:
                        embedmsg = discord.Embed(title="Error", description="You cannot offer more than your balance",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    # Add the amount to the trade
                    temp_user_data = active_trades.find_one({"trade_id": trade_id})["user_data"]
                    trade_current_user_data = temp_user_data[f"{message.author.id}"]
                    trade_current_user_data["balance"] += amount
                    temp_user_data[f"{message.author.id}"] = trade_current_user_data
                    active_trades.update_one({"trade_id": trade_id}, {"$set": {"user_data": temp_user_data}})
                    await update_display_trade_entries(trade_id)

                    return

                # Validate to make sure the player not only has the card, but also has enough cards that isn't already offered.

                # Try to get the card
                card_name_to_lookup = " ".join(args)

                # Check if the card exists in the card collection
                card_to_offer = card_collection.find_one({"name": card_name_to_lookup})
                if card_to_offer is None:
                    embedmsg = discord.Embed(title="Error", description="Invalid card name",
                                             color=embed_msg_color_error)
                    await message.channel.send(embed=embedmsg)
                    return

                # Check if the user has the card
                card_id = card_to_offer["card_id"]
                owned_cards = generated_cards_collection.find({"card_owner": message.author.id, "card_id": card_id})

                # Get number of copies of the card the user has
                card_count = 0
                for _ in owned_cards:
                    card_count += 1

                # Check if the offered cards is not higher than the number of cards the user has
                if card_count == 0:
                    embedmsg = discord.Embed(title="Error", description="You do not have the card",
                                             color=embed_msg_color_error)
                    await message.channel.send(embed=embedmsg)
                    return

                # Check if the user is not offering more cards than they have
                # Get the trade data
                temp_user_data = active_trades.find_one({"trade_id": trade_id})["user_data"]
                trade_current_user_data = temp_user_data[f"{message.author.id}"]
                num_of_item_copies = 0
                for item in trade_current_user_data["items"]:
                    if item == card_id:
                        num_of_item_copies += 1
                if num_of_item_copies >= card_count:
                    embedmsg = discord.Embed(title="Error", description="You cannot offer more cards than you have",
                                             color=embed_msg_color_error)
                    await message.channel.send(embed=embedmsg)
                    return

                # Add the card to the trade
                trade_current_user_data["items"].append(card_id)

                # Since the user added a card, unready both users
                for (user_id, user_data) in temp_user_data.items():
                    user_data["accept"] = False
                    temp_user_data[user_id] = user_data

                active_trades.update_one({"trade_id": trade_id}, {"$set": {"user_data": temp_user_data}})

                await update_display_trade_entries(trade_id)
                return
            if command == "remove":

                # Check args if the first symbol is "$"
                if args[0][0] == "$":
                    player_balance = user_collection.find_one({"discord_id": message.author.id})["balance"]
                    currently_offered_balance = \
                        active_trades.find_one({"trade_id": trade_id})["user_data"][f"{message.author.id}"]["balance"]
                    # Currently offered balance cannot be greater than the player's balance

                    try:
                        amount = int(args[0][1:])
                    except ValueError:
                        embedmsg = discord.Embed(title="Error", description="Invalid amount",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    if amount > currently_offered_balance:
                        embedmsg = discord.Embed(title="Error", description="You do not have enough balance",
                                                 color=embed_msg_color_error)
                        await message.channel.send(embed=embedmsg)
                        return
                    # Remove the amount from the trade
                    temp_user_data = active_trades.find_one({"trade_id": trade_id})["user_data"]
                    trade_current_user_data = temp_user_data[f"{message.author.id}"]
                    trade_current_user_data["balance"] -= amount
                    temp_user_data[f"{message.author.id}"] = trade_current_user_data
                    active_trades.update_one({"trade_id": trade_id}, {"$set": {"user_data": temp_user_data}})
                    await update_display_trade_entries(trade_id)
                    return

                # Allow the user to remove a card or balance from the trade

                # Try to get the card
                card_name_to_lookup = " ".join(args)

                # Check if the card exists in the card collection
                card_to_remove = card_collection.find_one({"name": card_name_to_lookup})
                if card_to_remove is None:
                    embedmsg = discord.Embed(title="Error", description="Invalid card name",
                                             color=embed_msg_color_error)
                    await message.channel.send(embed=embedmsg)
                    return

                # Check if the user has the card
                card_id = card_to_remove["card_id"]
                temp_user_data = active_trades.find_one({"trade_id": trade_id})["user_data"]
                trade_current_user_data = temp_user_data[f"{message.author.id}"]

                if card_id not in trade_current_user_data["items"]:
                    embedmsg = discord.Embed(title="Error", description="You do not have the card in the trade",
                                             color=embed_msg_color_error)
                    await message.channel.send(embed=embedmsg)
                    return

                # Remove the card from the trade
                trade_current_user_data["items"].remove(card_id)
                temp_user_data[f"{message.author.id}"] = trade_current_user_data
                active_trades.update_one({"trade_id": trade_id}, {"$set": {"user_data": temp_user_data}})
                await update_display_trade_entries(trade_id)

                return

            if command == "cancel":
                # Cancel the trade

                active_trades.delete_one({"trade_id": trade_id})
                await message.channel.delete()
                return

            if command == "accept":
                # Accept the trade

                # Get the trade data
                trade_current_user_data = active_trades.find_one({"trade_id": trade_id})["user_data"]
                trade_data_user = trade_current_user_data[f"{message.author.id}"]
                trade_data_user["accept"] = True
                trade_current_user_data[f"{message.author.id}"] = trade_data_user
                active_trades.update_one({"trade_id": trade_id}, {"$set": {"user_data": trade_current_user_data}})
                await update_display_trade_entries(trade_id)
                # Check if both users have accepted the trade
                if all(user_data["accept"] for user_data in trade_current_user_data.values()):
                    # Both users have accepted the trade
                    # Change the ownership of the cards

                    temp_list_user_data = list(trade_current_user_data.keys())

                    user1_id = int(temp_list_user_data[0])
                    user2_id = int(temp_list_user_data[1])
                    user3_placeholder = random.randint(100000000, 999999999)

                    # TODO DEBUG
                    print(f"User data: {temp_list_user_data}")

                    # Get the cards that are being traded
                    user1_cards = trade_current_user_data[str(user1_id)]["items"]
                    user2_cards = trade_current_user_data[str(user2_id)]["items"]

                    # Update the card owners

                    generated_cards_collection.update_many({"card_owner": user1_id, "card_id": {"$in": user1_cards}},
                                                           {"$set": {"card_owner": user3_placeholder}})
                    generated_cards_collection.update_many({"card_owner": user2_id, "card_id": {"$in": user2_cards}},
                                                           {"$set": {"card_owner": user1_id}})
                    generated_cards_collection.update_many(
                        {"card_owner": user3_placeholder, "card_id": {"$in": user1_cards}},
                        {"$set": {"card_owner": user2_id}})

                    # Update balances of each user, money is removed from each player and the amount is sent to other
                    user1_trade_balance = trade_current_user_data[str(user1_id)]["balance"]
                    user2_trade_balance = trade_current_user_data[str(user2_id)]["balance"]
                    user1_current_balance = user_collection.find_one({"discord_id": user1_id})["balance"]
                    user2_current_balance = user_collection.find_one({"discord_id": user2_id})["balance"]
                    user1_current_balance -= user1_trade_balance
                    user2_current_balance -= user2_trade_balance
                    user1_current_balance += user2_trade_balance
                    user2_current_balance += user1_trade_balance
                    user_collection.update_one({"discord_id": user1_id}, {"$set": {"balance": user1_current_balance}})
                    user_collection.update_one({"discord_id": user2_id}, {"$set": {"balance": user2_current_balance}})

                    # Send private messages to the users that the trade has been completed
                    for user_id in trade_current_user_data.keys():
                        member = await message.guild.fetch_member(int(user_id))
                        embedmsg = discord.Embed(title="Trade Completed", description="The trade has been completed",
                                                 color=embed_msg_color_success)
                        try:
                            await member.send(embed=embedmsg)
                        except HTTPException:
                            pass

                    # Delete the trade
                    active_trades.delete_one({"trade_id": trade_id})
                    await message.channel.delete()

                return

            # No subcommand was given, whoops
            embedmsg = discord.Embed(title="Error", description="Invalid subcommand", color=embed_msg_color_error)
            await message.channel.send(embed=embedmsg)
            return


async def update_display_trade_entries(trade_id: int):
    active_trades = database["active_trades"]
    trade_channel = discord.utils.get(client.get_all_channels(),
                                      id=active_trades.find_one({"trade_id": trade_id})["channel_id"])

    trade_data = active_trades.find_one({"trade_id": trade_id})["user_data"]
    monitor_msg = active_trades.find_one({"trade_id": trade_id})["monitor-id"]
    embedmsg = discord.Embed(title="Items offered", color=embed_msg_color_standard)
    for user_id, user_data in trade_data.items():
        member = await trade_channel.guild.fetch_member(int(user_id))
        item_list_counts = {}
        balance_offered = user_data["balance"]
        for item in user_data["items"]:
            card_details = card_collection.find_one({"card_id": item})
            this_card = Card.fromdict(card_details)
            if this_card.card_id not in item_list_counts:
                item_list_counts[this_card.card_id] = 1
            else:
                item_list_counts[this_card.card_id] += 1
        balance_placeholder = f"Balance: {balance_offered}"
        if len(item_list_counts) == 0:
            item_list_placeholder = "No items offered"
        else:
            item_list = []
            for card_id, count in item_list_counts.items():
                card_details = card_collection.find_one({"card_id": card_id})
                this_card = Card.fromdict(card_details)
                item_list.append(f"{this_card.name} x{count} ({this_card.rarity})")
            item_list_placeholder = "\n".join(item_list)
        final_list = f"{balance_placeholder}\n{item_list_placeholder}"

        # TODO DEBUG
        print(f"User name: {member.name}")
        print(f"User data: {user_data}")

        if user_data["accept"]:
            embedmsg.add_field(name=f"{member.name}'s items [Ready]", value=final_list, inline=False)
        else:
            embedmsg.add_field(name=f"{member.name}'s items", value=final_list, inline=False)
    monitor_msg_post = await trade_channel.fetch_message(monitor_msg)
    await monitor_msg_post.edit(content=None, embed=embedmsg)


def cmdhelp(category):
    if category == "debug":
        embedmsg = discord.Embed(title="Debug Command Reference", description="List of commands for the debug command",
                                 color=embed_msg_color_standard)
        embedmsg.add_field(name="!debug args", value="Displays the arguments given to the debug command", inline=True)
        embedmsg.add_field(name="!debug cardslist", value="Displays a list of all cards in the game", inline=True)
        embedmsg.add_field(name="!debug userslist", value="Displays a list of all users in the game", inline=True)
        embedmsg.add_field(name="!debug stafflist", value="Displays a list of all staff members", inline=True)
        embedmsg.add_field(name="!debug nuketrades", value="Deletes all active trades", inline=True)
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
    embedmsg.add_field(name="!buy cardpack <common/rare/epic/legendary/pay2win>",
                       value="Buys a card pack of the specified rarity", inline=True)
    embedmsg.add_field(name="!trade <user id>", value="Starts a trade with another user", inline=True)
    embedmsg.add_field(name="!claim", value="Claims a card", inline=True)
    embedmsg.add_field(name="!debug", value="Debug commands, for admin use only", inline=True)

    return embedmsg


@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')


client.run(token)
