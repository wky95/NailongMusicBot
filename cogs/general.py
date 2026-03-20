import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # @commands.command()
    # async def test(self, ctx):
    #     await ctx.send("這是修改前的容！")

async def setup(bot):
    await bot.add_cog(General(bot))