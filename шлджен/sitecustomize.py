"""Optional startup module.

The bot extensions are installed by start_bot.py after DB and Dispatcher
exist. This module intentionally does NOT monkey-patch Dispatcher.include_router:
the previous patch caused TypeError when aiogram passed the router arguments.
"""
