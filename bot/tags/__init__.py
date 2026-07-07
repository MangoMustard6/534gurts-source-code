from .cog import TagCog


async def setup(bot):
    await bot.add_cog(TagCog(bot))
