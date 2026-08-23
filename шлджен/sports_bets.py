"""Minimal additive patch: outcome betting for Telegram darts and bowling.
Does not replace the existing game flow; it only intercepts darts/bowling starts
and adds a dedicated outcome-selection callback.
"""
import asyncio
import sys
import time
from decimal import Decimal
from aiogram import F
from aiogram.utils.keyboard import InlineKeyboardBuilder

_INSTALLED_ROUTERS = set()
_ORIGINAL_START = None

DARTS = {
    "miss": {1},
    "white": {2, 4},
    "red": {3, 5},
    "center": {6},
}
BOWLING = {
    "miss": {1},
    "pins1": {2},
    "pins2": {3},
    "pins3": {4},
    "pins4": {5},
    "strike": {6},
}


def _ctx():
    return sys.modules.get("__main__")


def _fmt(x):
    return f"{Decimal(str(x)):,.0f}".replace(",", "'")


def _cur(a):
    return a.currency_primary()


def _sep(a):
    return getattr(a, "SEP", "·····················")


def _label(game, choice):
    if game == "darts":
        return {
            "white": "⚪ Белое",
            "red": "🔴 Красное",
            "miss": "❌ Мимо",
            "center": "🎯 Центр",
        }[choice]
    return {
        "strike": "💥 Страйк",
        "miss": "❌ Мимо",
        "pins1": "1 кегля",
        "pins2": "2 кегли",
        "pins3": "3 кегли",
        "pins4": "4 кегли",
    }[choice]


def _choice_keyboard(uid, game, amount):
    b = InlineKeyboardBuilder()
    if game == "darts":
        choices = [
            ("⚪ Белое", "white"),
            ("🔴 Красное", "red"),
            ("❌ Мимо", "miss"),
            ("🎯 Центр", "center"),
        ]
    else:
        choices = [
            ("💥 Страйк", "strike"),
            ("❌ Мимо", "miss"),
            ("1 кегля", "pins1"),
            ("2 кегли", "pins2"),
            ("3 кегли", "pins3"),
            ("4 кегли", "pins4"),
        ]
    for text, choice in choices:
        b.button(text=text, callback_data=f"sportbet:{uid}:{game}:{choice}:{amount}")
    b.button(text="◀️ Назад", callback_data=f"gx:{uid}:game:{game}")
    b.adjust(2, 2, 2 if game == "bowling" else 1, 1)
    return b.as_markup()


async def _start_sport_choice(uid, game, amount, message):
    a = _ctx()
    amount = Decimal(str(amount))
    title = "🎯 <b>ДАРТС</b>" if game == "darts" else "🎳 <b>БОУЛИНГ</b>"
    prompt = "Куда попадёт дартс?" if game == "darts" else "Что угадываем?"
    text = (
        f"{title}\n`{_sep(a)}`\n\n"
        f"{prompt}\n\n"
        f"💰 Ставка: <b>{_fmt(amount)} {_cur(a)}</b>"
    )
    return await a.show(message, text, _choice_keyboard(uid, game, amount))


async def _sport_roll(c, uid, game, choice, amount):
    a = _ctx()
    db, games, bot = a.db, a.games, a.bot
    amount = Decimal(str(amount))

    if c.from_user.id != int(uid):
        return await c.answer()
    if amount <= 0 or amount != amount.to_integral_value():
        return await c.answer("❌ Некорректная ставка.", show_alert=True)
    if db.balance(uid)[0] < amount:
        return await c.answer(f"❌ Недостаточно {_cur(a)}.", show_alert=True)

    if not games.cost(uid, amount, game + "_bet"):
        return await c.answer(f"❌ Недостаточно {_cur(a)}.", show_alert=True)

    emoji = "🎯" if game == "darts" else "🎳"
    try:
        msg = await bot.send_dice(c.message.chat.id, emoji=emoji)
        await asyncio.sleep(2)
        value = int(msg.dice.value)
    except Exception:
        db.add(uid, "Goldcoin", amount, game + "_refund")
        raise

    mapping = DARTS if game == "darts" else BOWLING
    win = value in mapping.get(choice, set())
    payout = amount * Decimal(db.setting("sport_multiplier") or "2") if win else Decimal(0)
    result_label = _label(game, choice)

    games.finish(uid, game, amount, f"{choice};roll:{value}", payout, win)

    if game == "darts":
        actual = {1: "❌ Мимо", 2: "⚪ Белое", 3: "🔴 Красное", 4: "⚪ Белое", 5: "🔴 Красное", 6: "🎯 Центр"}[value]
    else:
        actual = {1: "❌ Мимо", 2: "1 кегля", 3: "2 кегли", 4: "3 кегли", 5: "4 кегли", 6: "💥 Страйк"}[value]

    text = (
        f"{emoji} <b>{'ДАРТС' if game == 'darts' else 'БОУЛИНГ'}</b>\n"
        f"`{_sep(a)}`\n\n"
        f"Твой выбор: <b>{result_label}</b>\n"
        f"Выпало: <b>{actual}</b>\n\n"
        + (
            f"🎉 <b>Победа!</b>\n💰 +{_fmt(payout)} {_cur(a)}"
            if win
            else f"❌ <b>Не угадал!</b>\n💸 −{_fmt(amount)} {_cur(a)}"
        )
        + f"\n\n{a.bal(uid)}"
    )
    return await bot.send_message(
        c.message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=a.result_k(f"game:{game}"),
    )


async def _callback(c):
    d = c.data or ""
    if not d.startswith("sportbet:"):
        return
    p = d.split(":", 4)
    if len(p) != 5:
        return await c.answer()
    _, uid, game, choice, amount = p
    if c.from_user.id != int(uid) or game not in ("darts", "bowling"):
        return await c.answer()
    await c.answer()
    return await _sport_roll(c, int(uid), game, choice, Decimal(amount))


def _patch_start(vx):
    global _ORIGINAL_START
    if getattr(vx._start_bet, "_sport_bets_wrapped", False):
        return
    _ORIGINAL_START = vx._start_bet

    async def wrapped(uid, game, amount, chat_id, message):
        if game in ("darts", "bowling"):
            return await _start_sport_choice(uid, game, amount, message)
        return await _ORIGINAL_START(uid, game, amount, chat_id, message)

    wrapped._sport_bets_wrapped = True
    vx._start_bet = wrapped


def _patch_router():
    a = _ctx()
    vx = sys.modules.get("bot_extensions_v2")
    if not a or not vx or not hasattr(a, "r"):
        return
    _patch_start(vx)
    router = a.r
    key = id(router)
    if key in _INSTALLED_ROUTERS:
        return
    router.callback_query.register(_callback, F.data.startswith("sportbet:"))
    try:
        router.callback_query.handlers.insert(0, router.callback_query.handlers.pop())
    except Exception:
        pass
    _INSTALLED_ROUTERS.add(key)
    print("[EXT] Darts/bowling outcome betting loaded.", flush=True)


def watch():
    while True:
        try:
            _patch_router()
        except Exception:
            pass
        time.sleep(0.25)


def start():
    import threading
    t = threading.Thread(target=watch, daemon=True, name="hold-sport-bets")
    t.start()
