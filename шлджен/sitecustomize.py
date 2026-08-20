import sys
import asyncio
from decimal import Decimal, InvalidOperation

try:
    from aiogram import Router, Dispatcher
except Exception:
    Router = Dispatcher = None

if Router is not None and Dispatcher is not None:
    kw = Router(name='goldgame_keywords')
    original_include = Dispatcher.include_router
    installed = False

    def app():
        # start_bot.py executes bot.py as __main__.
        return sys.modules.get('__main__') or sys.modules.get('bot')

    actions = {
        'б': 'balance', 'бал': 'balance', 'баланс': 'balance',
        'проф': 'profile', 'профиль': 'profile',
        'реф': 'ref', 'рефы': 'ref', 'реферал': 'ref', 'рефералы': 'ref',
        'топ': 'top', 'игры': 'play', 'игра': 'play', 'плей': 'play',
        'бонус': 'bonus', 'дейли': 'daily', 'ежедневный': 'daily', 'ежедневка': 'daily',
        'лот': 'lottery', 'лотерея': 'lottery',
        'кейс': 'cases', 'кейсы': 'cases',
        'перевод': 'transfer', 'перевести': 'transfer',
        'обмен': 'exchange', 'обменник': 'exchange',
        'заработать': 'earn', 'заработок': 'earn',
        'промо': 'promo', 'промокод': 'promo',
        'донат': 'donate', 'хелп': 'help', 'помощь': 'help',
        'правила': 'rules', 'админ': 'admin', 'админка': 'admin'
    }

    games = {
        'баскет': ('basket', '🏀'), 'баскетбол': ('basket', '🏀'), 'бск': ('basket', '🏀'),
        'футбол': ('football', '⚽'), 'фут': ('football', '⚽'), 'фтб': ('football', '⚽'),
        'дартс': ('darts', '🎯'), 'дрт': ('darts', '🎯'),
        'боулинг': ('bowling', '🎳'), 'боул': ('bowling', '🎳'), 'бл': ('bowling', '🎳'),
        'кубик': ('dice', '🎲'), 'куб': ('dice', '🎲'), 'кб': ('dice', '🎲'),
        'монета': ('coin', '🪙'), 'мон': ('coin', '🪙'), 'мт': ('coin', '🪙'),
        'спин': ('spin', '🎰'), 'сп': ('spin', '🎰'),
        'мины': ('mines', '💣'), 'мина': ('mines', '💣'), 'мн': ('mines', '💣'),
        '21': ('21', '🃏'), 'двадцатьодин': ('21', '🃏'),
        'башня': ('tower', '🗼'), 'бш': ('tower', '🗼'),
        'кости': ('dice2', '🎲'), 'кст': ('dice2', '🎲')
    }

    def keyword_filter(m):
        text = (getattr(m, 'text', None) or '').strip()
        if not text or text.startswith('/') or not getattr(m, 'from_user', None):
            return False
        a = app()
        if a is None or getattr(a, 'state', {}).get(m.from_user.id):
            return False
        parts = text.lower().split()
        if len(parts) == 1:
            return parts[0] in actions or parts[0] in games
        if len(parts) == 2 and parts[0] in games:
            try:
                Decimal(parts[1].replace("'", '').replace(',', '.'))
                return True
            except Exception:
                return False
        return False

    async def handler(m):
        a = app()
        text = m.text.strip()
        low = text.lower()
        uid = m.from_user.id
        parts = low.split()

        if parts[0] in games:
            game, emoji = games[parts[0]]
            if len(parts) != 2:
                return await m.answer(f'{emoji} Укажи ставку. Пример: <b>{parts[0]} 500</b>', parse_mode='HTML')
            try:
                bet = Decimal(parts[1].replace("'", '').replace(',', '.'))
            except InvalidOperation:
                return await m.answer('❌ Неверная ставка. Пример: <b>баскет 500</b>', parse_mode='HTML')
            if bet <= 0 or bet != bet.to_integral_value():
                return await m.answer('❌ Ставка должна быть положительным целым числом.')
            bet = int(bet)
            balance = a.db.balance(uid)[0]
            if balance < bet:
                return await m.answer(f'❌ <b>Недостаточно средств.</b>\n\n💰 Баланс: <b>{a.fmt(balance)} {a.currency_primary()}</b>\n🎯 Ставка: <b>{a.fmt(bet)} {a.currency_primary()}</b>', parse_mode='HTML')

            if game in ('basket', 'football', 'darts', 'bowling'):
                dice_emoji = {'basket':'🏀','football':'⚽','darts':'🎯','bowling':'🎳'}[game]
                roll = await a.bot.send_dice(m.chat.id, emoji=dice_emoji)
                await asyncio.sleep(2)
                result = a.games.sports(uid, game, bet, roll.dice.value)
                if result is None:
                    return await m.answer('❌ Не удалось сделать ставку. Недостаточно средств.')
                win, payout = result
                title = {'basket':'БАСКЕТБОЛ','football':'ФУТБОЛ','darts':'ДАРТС','bowling':'БОУЛИНГ'}[game]
                result_text = '🎯 <b>ПОПАЛ!</b>' if win else '❌ <b>МИМО!</b>'
                money = f'🎉 Выигрыш: +{a.fmt(payout)}' if win else f'💸 Проигрыш: −{a.fmt(bet)}'
                return await m.answer(f'{dice_emoji} <b>{title}</b>\n{a.SEP}\n\n{result_text}\n{money} {a.currency_primary()}\n\n{a.bal(uid)}', parse_mode='HTML')

            if game == 'dice':
                return await m.answer(f'🎲 <b>КУБИК</b>\n{a.SEP}\n\nВыбери число от 1 до 6:\n\nСтавка: <b>{a.fmt(bet)} {a.currency_primary()}</b>', parse_mode='HTML', reply_markup=a.dice_guess_k(bet))
            if game == 'dice2':
                return await m.answer(f'🎲 <b>КОСТИ</b>\n{a.SEP}\n\nВыбери условие и число:\n\nСтавка: <b>{a.fmt(bet)} {a.currency_primary()}</b>', parse_mode='HTML', reply_markup=a.dice_condition_k(bet))
            if game == 'coin':
                return await m.answer(f'🪙 <b>МОНЕТА</b>\n{a.SEP}\n\nВыбери сторону:\n\nСтавка: <b>{a.fmt(bet)} {a.currency_primary()}</b>', parse_mode='HTML', reply_markup=a.coin_k(bet))
            if game == '21':
                g = a.games.blackjack_start(uid, bet)
                if not g:
                    return await m.answer('❌ Не удалось начать игру. Недостаточно средств или игра уже идёт.')
                return await a.show(m, a.bj_text(g, hide=True), a.bj_k())
            if game == 'mines':
                if not a.games.mines_start(uid, bet):
                    return await m.answer('❌ Не удалось начать игру. Недостаточно средств или игра уже идёт.')
                return await a.show(m, '💣 <b>МИНЫ</b>\n' + a.SEP + f'\n\n💰 Ставка: <b>{a.fmt(bet)} {a.currency_primary()}</b>\n\nОткрывай клетки:', a.mines_k(a.games.mines[uid]))
            if game == 'tower':
                if not a.games.tower_start(uid, bet):
                    return await m.answer('❌ Не удалось начать игру. Недостаточно средств или игра уже идёт.')
                return await a.show(m, '🗼 <b>БАШНЯ</b>\n' + a.SEP + f'\n\n💰 Ставка: <b>{a.fmt(bet)} {a.currency_primary()}</b>', a.tower_k())
            return

        action = actions.get(low)
        if not action:
            return
        funcs = {
            'balance': lambda: m.answer(a.bal(uid), parse_mode='HTML'),
            'profile': lambda: a.profile(m), 'ref': lambda: a.ref(m),
            'top': lambda: a.top(m), 'play': lambda: a.play(m),
            'bonus': lambda: a.bonus(m), 'daily': lambda: a.daily(m),
            'lottery': lambda: a.open_lottery(m), 'cases': lambda: a.cases(m),
            'transfer': lambda: a.transfer_open(m), 'exchange': lambda: a.exchange_open(m),
            'earn': lambda: a.earn_open(m), 'donate': lambda: a.donate(m),
            'help': lambda: a.help_cmd(m), 'rules': lambda: a.rules(m)
        }
        if action == 'promo':
            a.state[uid] = {'promo': True}
            return await m.answer(f'🎟 <b>ПРОМОКОД</b>\n{a.SEP}\n\nВведите промокод:', parse_mode='HTML', reply_markup=a.one_back('home'))
        if action == 'admin':
            if not a.is_admin(uid):
                return await m.answer('⛔ Нет доступа.')
            return await m.answer('👑 <b>АДМИН-ПАНЕЛЬ</b>', parse_mode='HTML', reply_markup=a.admin_k())
        fn = funcs.get(action)
        if fn:
            return await fn()

    # The filter is critical: a catch-all handler would swallow /commands.
    kw.message.register(handler, keyword_filter)

    def patched_include(self, router):
        global installed
        if not installed and router is not kw:
            original_include(self, kw)
            installed = True
        return original_include(self, router)

    Dispatcher.include_router = patched_include
