import asyncio
import os
import sys
import time
from threading import Thread

import discord
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('ALT_DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

list_of_guilds = []

# Default values
current_guild = 1200179990646501440  # Test Guild
current_channel = 1252097663265144862  # 'test' channel

client_is_ready = False


@client.event
async def on_ready():
    global client_is_ready
    print(f'{client.user} has connected to Discord!')
    print(f'Connected to the following guilds:')
    for guild in client.guilds:
        print(f'{guild.name} (id: {guild.id})')
        list_of_guilds.append(guild.id)
    print("--------------------")
    print(f'Current guild: {current_guild}')
    print(f'Name of current guild: {client.get_guild(current_guild).name}')
    print("--------------------")
    print(f'List of channels in current guild:')
    for channel in client.get_guild(current_guild).channels:
        print(f'{channel.name} (id: {channel.id})')
    print("--------------------")
    print(f'Current channel: {client.get_channel(current_channel).name} - ({current_channel})')
    print("--------------------")
    print(f'Type "help" for a list of commands')
    client_is_ready = True


@client.event
async def on_message(message):
    global chat_client
    if message.author == client.user:
        return
    # Interrupt the main thread if a message is received
    chat_client.receive_message(message)


class ChatClient:
    def __init__(self, client):
        self.client = client
        self.current_guild = 1200179990646501440  # Test Guild
        self.current_channel = 1252097663265144862  # 'test' channel
        self.input_thread = Thread(target=self.wait_for_input)
        self.input_thread.start()

    def wait_for_input(self):
        while True:
            user_input = input("> ")
            self.process_input(user_input)

    def receive_message(self, message):
        print(f'\n{message.guild}] {message.author}: {message.content}')
        # No new line after > prompt
        print("> ", end="")

    def process_input(self, raw_input):
        command = raw_input.split(" ")[0]
        args = raw_input.split(" ")[1:]
        if command == "exit":
            print("Goodbye")
            asyncio.run_coroutine_threadsafe(client.close(), client.loop)
            sys.exit(0)
        elif command == "setguild":
            # Set the current guild based on id
            try:
                current_guild = int(args[0])
                print(f'Current guild: {current_guild}')
                print(f'Name of current guild: {client.get_guild(current_guild).name}')
                print(f'List of channels in current guild:')
                for channel in client.get_guild(current_guild).channels:
                    print(f'{channel.name} (id: {channel.id})')
                current_channel = client.get_guild(current_guild).channels[0].id
                print(f'Current channel: {client.get_channel(current_channel).name} - ({current_channel})')
            except Exception as e:
                print("Invalid guild id")
        elif command == "setchannel":
            # Set the current channel based on id
            try:
                current_channel = int(args[0])
                print(f'Current channel: {current_channel}')
                print(f'Name of current channel: {client.get_channel(current_channel).name}')
            except:
                print("Invalid channel id")
        elif command == "listguilds":
            # List all guilds
            try:
                for guild in client.guilds:
                    print(f'{guild.id} - {guild.name}')
            except:
                print("Error listing guilds")
        elif command == "listchannels":
            # List all channels in current guild
            try:
                for channel in client.get_guild(self.current_guild).channels:
                    print(f'{channel.id} - {channel.name}')
            except:
                print("Error listing channels")
        elif command == "chat":
            # Send a message to the current channel
            try:
                # await client.get_channel(self.current_channel).send(" ".join(args))
                asyncio.run_coroutine_threadsafe(client.get_channel(self.current_channel).send(" ".join(args)), client.loop)

            except Exception as e:
                print("Error sending message")
                print(e)
        elif command == "msg":
            # Private message a user
            target = args[0]
            # Is the target a user id or a user name?
            try:
                target = int(target)
            except:
                target = target
            if isinstance(target, int):
                target = client.get_user(target)
            else:
                # Try to find an id based on the either name or part of the name
                for user in client.get_all_members():
                    if target.lower() in user.name.lower():
                        target = user
                        break
            try:
                # await target.send(" ".join(args[1:]))
                asyncio.run_coroutine_threadsafe(target.send(" ".join(args[1:])), client.loop)


            except Exception as e:
                print("Error sending message")
                print(e)


        elif command == "help":
            print("Commands:")
            print("setguild <id> - Set the current guild")
            print("setchannel <id> - Set the current channel")
            print("listguilds - List all guilds")
            print("listchannels - List all channels in current guild")
            print("chat <message> - Send a message to the current channel")
            print("msg <id> <message> - Send a private message to a user")
            print("exit - Exit the program")
        elif command[0] == "!":
            command_text = raw_input
            asyncio.run_coroutine_threadsafe(client.get_channel(self.current_channel).send(command_text), client.loop)
        elif command != "":
            print("Invalid command - type 'help' for a list of commands")
        print("--------------------")

async def client_chat(client, channelid, message):
    await client.get_channel(channelid).send(message)



Thread(target=client.run, args=(token,)).start()
# pause for a second to let the bot connect
time.sleep(3)

chat_client = ChatClient(client)
