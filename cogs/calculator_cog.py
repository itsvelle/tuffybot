
from discord.ext import commands
import operator

class CalculatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.operators = {
            '+': operator.add,
            '-': operator.sub,
            '*': operator.mul,
            '/': operator.truediv,
            '%': operator.mod,
            '^': operator.pow,
        }

    @commands.hybrid_command(name="calc", description="Performs a simple calculation.")
    async def calculate(self, ctx: commands.Context, expression: str):
        """
        Performs a simple calculation.
        Example: /calc 5+3*2
        """
        try:
            # Basic sanitization: only allow digits, operators, parentheses, and spaces
            allowed_chars = "0123456789.+-*/%^() "
            if not all(c in allowed_chars for c in expression):
                await ctx.send("Invalid characters detected in the expression. Only digits, basic operators (+-*/%^), parentheses, and spaces are allowed.")
                return

            # Evaluate the expression
            # WARNING: Using eval() can be dangerous if input is not strictly controlled.
            # For a simple calculator, with the above sanitization, it's generally acceptable
            # for basic arithmetic. For more complex/secure applications, a dedicated
            # math expression parser library (e.g., SymPy, asteval) should be used.
            result = eval(expression)
            await ctx.send(f"Result: `{expression} = {result}`")
        except SyntaxError:
            await ctx.send("Invalid expression syntax. Please check your input.")
        except ZeroDivisionError:
            await ctx.send("*explodes 💥*\n-# (you can't divide by zero)")
        except Exception as e:
            await ctx.send(f"An error occurred during calculation: `{e}`")

async def setup(bot):
    await bot.add_cog(CalculatorCog(bot))
