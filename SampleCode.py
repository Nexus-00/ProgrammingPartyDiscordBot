# bot.py
import os
import asyncio
import discord
from dotenv import load_dotenv
from discord import app_commands ##command tree function and allows discord commands to rec command
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


MY_GUILD = discord.Object(os.getenv('5S_GUILD')) ## convert to discord token

class MyClient(discord.Client):
    ##constructor
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)

intents = discord.Intents.default()
client = MyClient(intents = intents)

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

##start a command with a tree
##function async def 

@client.tree.command() ##slash command
async def reply(interaction: discord.Interaction, hobby: str):
    ##print("Hello, there") ## have to use a send message instead to console
    await interaction.response.send_message(f'How is it going {interaction.user.mention}. Thats a cool hobby TFTI: your hobby is {hobby}') ##await interaction sends to discord w/e inside {} is value sent 


##timer stuff helped
##change time_to_trigger to the time in pacific time zone when task starts
##my_task() to perform action at wanted time



##sending a discord embed, update it every 5 seconds or second
##have the return instead updating embed
##look into python scheduler, start and send message at x ammount of time. schedule.every 
##don't use returns, use a flag to set true or false
##method called wait
def timer(timeInput): 
    try:
        try:
            time = int(timeInput)
        except:
            convertTimeList = {'s':1, 'm':60, 'h':3600, 'd':86400, 'S':1, 'M':60, 'H':3600, 'D':86400}
            time = int(timeInput[:-1]) * convertTimeList[timeInput[-1]]
        if time > 86400:
            return "I can\'t do timers over a day long" ##returns take me out of fuction but want to stay in function so timer will count down
        if time <= 0:
            
            return "Timers don\'t go into negatives :/"
        if time >= 3600:
            return f"Timer: {time//3600} hours {time%3600//60} minutes {time%60} seconds"
           
        elif time >= 60:
            return f"Timer: {time//60} minutes {time%60} seconds"
            
        elif time < 60:
            return f"Timer: {time} seconds"
            
        while True:
            try:
                return asyncio.sleep(5)
                time -= 5
                if time >= 3600:
                    return f"Timer: {time//3600} hours {time %3600//60} minutes {time%60} seconds"
                elif time >= 60:
                    return f"Timer: {time//60} minutes {time%60} seconds"
                elif time < 60:
                    return f"Timer: {time} seconds"
                if time <= 0:
                    zero(time)
                    return "{ctx.author.mention} Your countdown Has ended!"
                    break
            except:
                break
    except:
        return "Alright, first you gotta let me know how I\'m gonna time **{timeInput}**...."


async def zero(ctx,time):
    try:
        # Code that might raise asyncio.TimeoutError
        if time == 0:
            await asyncio.wait_for(some_coroutine(), timeout=0)
    except asyncio.TimeoutError:
        await ctx.send(f"{ctx.author.mention} countdown finished") ##ctx.author.mention discord @mention

@client.tree.command()
async def test(interaction: discord.Interaction, time: int):
    message = timer(timeInput = time) ##put a variable here, for timer input by user.
    await interaction.response.send_message(f'Just a reminder {interaction.user.mention}. That the cooldown for timer is up {message}') 
    ##look up helper method

    ##sending an alert when timer hits zero.
    ##mention user when ping timer hits zero.




##discord calls a slash a command a tree command

client.run(TOKEN) 