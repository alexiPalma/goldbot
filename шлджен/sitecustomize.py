"""Keyword router for GoldGame.

Loaded automatically by Python when bot.py is started from this directory.
It is intentionally isolated from bot.py so the existing 60KB handler file does
not need to be rewritten just to add keyword commands.
"""

import sys
from decimal import Decimal, InvalidOperation

try:
    from aiogram import Router
    from aiogram.dispatcher.dispatcher import Dispatcher
except Exception:
    Router = None
    Dispatcher = None


if Router is not None and Dispatcher is not None:
    _keyword_router = Router(name="goldgame_keywords")
    _original_include_router = Dispatcher.include_router
    _installed = False

    def _app():
        """Find the running bot module without assuming its filename."""
        for mod in list(sys.modules.values()):
            if mod is None:
                continue
            if all(hasattr(mod, x) for x in ("db", "games", "bot", "state")):
                return mod
        return None

    def _one_arg_action(text):
        return {
            "б": "balance",
            "баланс": "balance",
            "бал": "balance",
            "профиль": "profile",
            "проф": "profile",
            "реф": "ref",
            "рефы": "ref",
            "реферал": "ref",
            "рефералы": "ref",
            "топ": "top",
            "игры": "play",
            "игра": "play",
            "плей": "play",
            "бонус": "bonus",
            "дейли": "daily",
            "ежедневный": "daily",
            "ежедневка": "daily",
            "лотерея": "lottery",
            "лот": "lottery",
            "кейсы": "cases",
            "кейс": "cases",
            "перевод": "transfer",
            "перевести": "transfer",
            "обмен": "exchange",
            "обменник": "exchange",
            "заработать": "earn",
            "заработок": "earn",
            "промо": "promo",
            "промокод": "promo",
            "донат": "donate",
            "хелп": "help",
            "помощь": "help",
            "правила": "rules",
            "админ": "admin",
            "админка": "admin",
        }.get(text)

    _games = {
        "баскет": "basket",
        "баскетбол": "basket",
        "футбол": "football",
        "фут": "football",
        "дартс": "darts",
        "кубик": "dice",
        "куб": "dice",
        "боулинг": "bowling",
        "боул": "bowling",
        "спин": "spin",
        "мины": "mines",
        "мина": "mines",
        "21": "21",
        "башня": "tower",
        "монета": "coin",
        "кости": "dice2",
    }

    def _keyword_match(m):
        text = (getattr(m, "text", None) or "").strip().lower()
        if not text or text.startswith("/"):
            return False
        app = _app()
        if app is not None and app.state.get(m.from_user.id):
            return False
        parts = text.split()
        if len(parts) == 1:
            return bool(_one_arg_action(parts[0]) or parts[0] in _games)
        if len(parts) == 2 and parts[0] in _games:
            try:
                Decimal(parts[1].replace("'", "").replace(",", "."))
                return True
            except Exception:
                return False
        return False

    async def _call(app, names, message):
        for name in names:
            fn = getattr(app, name, None)
            if fn is not None:
                return await fn(message)
        return None

    async def _open_game(app, m, game, bet):
        uid = m.from_user.id
        if bet is None:
            labels = {
                "basket": "🏀 Баскетбол", "football": "⚽ Футбол",
                "darts": "🎯 Дартс", "dice": "🎲 Кубик",
                "bowling": "🎳 Боулинг", "spin": "🎰 Спин",
                "mines": "💣 Мины", "21": "🃏 21 очко",
                "tower": "🗼 Башня", "coin": "🪙 Монета", "dice2": "🎲 Кости",
            }
            return await m.answer(
                f"{labels[game]}\n{app.SEP}\n\nВыбери ставку:",
                parse_mode="HTML", reply_markup=app.bet_k(game)
            )

        bet = Decimal(str(bet))
        if bet <= 0 or bet != bet.to_integral_value():
            return await m.answer("❌ Ставка должна быть положительным целым числом.")
        bet = int(bet)

        balance = app.db.balance(uid)[0]
        if balance < bet:
            return await m.answer(
                f"❌ <b>Недостаточно {app.html.escape(app.currency_primary())}</b>\n"
                f"\nТвой баланс: <b>{app.fmt(balance)} {app.html.escape(app.currency_primary())}</b>\n"
                f"Требуется: <b>{app.fmt(bet)} {app.html.escape(app.currency_primary())}</b>",
                parse_mode="HTML"
            )

        if game in ("basket", "football", "darts", "bowling"):
            return await app.sports_game(m, game, Decimal(bet))
        if game == "spin":
            return await app.spin_game(m, Decimal(bet))
        if game == "dice":
            return await m.answer(
                f"🎲 <b>КУБИК</b>\n{app.SEP}\n\n"
                f"Загадай число от <b>1 до 6</b>.\n\n"
                f"Ставка: <b>{app.fmt(bet)} {app.currency_primary()}</b>",
                parse_mode="HTML", reply_markup=app.dice_guess_k(bet)
            )
        if game == "dice2":
            return await m.answer(
                f"🎲 <b>КОСТИ</b>\n{app.SEP}\n\nВыбери условие и число:\n\n"
                f"Ставка: <b>{app.fmt(bet)} {app.currency_primary()}</b>",
                parse_mode="HTML", reply_markup=app.dice_condition_target_k(bet)
            )
        if game == "coin":
            return await m.answer(
                f"🪙 <b>МОНЕТА</b>\n{app.SEP}\n\nВыбери сторону:\n\n"
                f"Ставка: <b>{app.fmt(bet)} {app.currency_primary()}</b>",
                parse_mode="HTML", reply_markup=app.coin_k(bet)
            )
        if game == "21":
            g = app.games.blackjack_start(uid, bet)
            if not g:
                return await m.answer("❌ Не удалось начать игру. Возможно, 21 уже идёт.")
            return await app.show(m, app.bj_text(g, hide=True), app.bj_k())
        if game == "mines":
            if not app.games.mines_start(uid, bet):
                return await m.answer("❌ Игра уже идёт или ставка недоступна.")
            g = app.games.mines[uid]
            return await app.show(
                m,
                f"💣 <b>МИНЫ</b>\n{app.SEP}\n\n"
                f"💰 Ставка: <b>{app.fmt(bet)} {app.currency_primary()}</b>\n"
                f"💣 Мин: <b>3</b>\n\nОткрывай клетки. Бомба заканчивает игру.",
                app.mines_k(g)
            )
        if game == "tower":
            if not app.games.tower_start(uid, bet):
                return await m.answer("❌ Игра уже идёт или ставка недоступна.")
            return await app.show(
                m,
                f"🗼 <b>БАШНЯ</b>\n{app.SEP}\n\n"
                f"💰 Ставка: <b>{app.fmt(bet)} {app.currency_primary()}</b>\n"
                f"📍 Высота: <b>1 / 6</b>\n\n"
                f"В каждом ряду одна бомба. Поднимайся выше или забирай выигрыш.",
                app.tower_k()
            )

    async def _keyword_handler(m):
        app = _app()
        if app is None:
            return
        text = (m.text or "").strip().lower()
        parts = text.split()

        if len(parts) >= 1 and parts[0] in _games:
            bet = None
            if len(parts) == 2:
                try:
                    bet = Decimal(parts[1].replace("'", "").replace(",", "."))
                except InvalidOperation:
                    return await m.answer("❌ Неверная ставка. Пример: <b>баскет 500</b>", parse_mode="HTML")
            return await _open_game(app, m, _games[parts[0]], bet)

        action = _one_arg_action(text)
        if not action:
            return

        uid = m.from_user.id
        if action == "balance":
            return await m.answer(app.bal(uid), parse_mode="HTML")
        if action == "profile":
            return await m.answer(app.profile_text(uid), parse_mode="HTML", reply_markup=app.one_back("home"))
        if action == "ref":
            return await m.answer(app.ref_text(uid), parse_mode="HTML", reply_markup=app.one_back("home"))
        if action == "top":
            return await m.answer(app.top_text(), parse_mode="HTML", reply_markup=app.one_back("home"))
        if action == "play":
            return await m.answer(app.play_text(), parse_mode="HTML", reply_markup=app.play_k())
        if action == "bonus":
            return await app.bonus(m)
        if action == "daily":
            return await app.daily(m)
        if action == "lottery":
            return await app.open_lottery(m)
        if action == "cases":
            return await app.cases(m)
        if action == "transfer":
            return await app.transfer_open(m)
        if action == "exchange":
            return await app.exchange_open(m)
        if action == "earn":
            return await app.earn_open(m)
        if action == "donate":
            return await app.donate(m)
        if action == "help":
            return await app.help_cmd(m)
        if action == "rules":
            return await app.rules(m)
        if action == "promo":
            app.state[uid] = {"promo": True}
            return await m.answer(
                f"🎟 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n{app.SEP}\n\nВведите промокод сообщением ниже.",
                parse_mode="HTML", reply_markup=app.one_back("home")
            )
        if action == "admin":
            if not app.is_admin(uid):
                return await m.answer("⛔ Нет доступа.")
            return await app.show(
                m,
                f"👑 <b>АДМИН-ПАНЕЛЬ</b>\n{app.SEP}\n\nВыбери действие:",
                app.admin_k()
            )

    _keyword_router.message.register(_keyword_handler, _keyword_match)

    def _include_router(self, router):
        global _installed
        if not _installed and self is not _keyword_router:
            _original_include_router(self, _keyword_router)
            _installed = True
        return _original_include_router(self, router)

    Dispatcher.include_router = _include_router
