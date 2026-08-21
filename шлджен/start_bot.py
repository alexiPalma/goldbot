import os
import runpy
import time
import traceback
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(BASE, 'bot.py')

# Inject the keyword router into bot.py immediately before its polling starts.
# This avoids the old startup monkey-patches and guarantees that the router
# exists after DB, state, commands and callbacks have all been created.
KEYWORDS = r'''

# ---------- universal keyword router ----------
from aiogram.dispatcher.event.bases import SkipHandler as _HoldSkipHandler


def _hold_norm(text):
    return ' '.join((text or '').strip().lower().split())


def _hold_keyword_match(text):
    t=_hold_norm(text)
    if not t or t.startswith('/'):
        return False
    p=t.split()
    singles={
        'б','баланс','банк','профиль','проф','реф','реферал','рефералы','топ',
        'заработать','заработок','обменник','обмен','помощь','хелп','help',
        'правила','игры','игра','кейсы','кейсы','бонус','ежедневный','дейли',
        'лотерея','перевод','донат','промо','промокод',
        'баскет','баскетбол','бск','фтб','футбол','сп','спин','дартс','дрс',
        'кубик','куб','боулинг','бол','минута','мины','мина','21','блэкджек',
        'башня','монета','мон','кости','кейс'
    }
    if t in singles:
        return True
    if len(p)>=2 and p[0] in {
        'баскет','баскетбол','бск','фтб','футбол','сп','спин','дартс','дрс',
        'кубик','куб','боулинг','бол','мины','мина','21','башня','монета','мон',
        'кости','кейс','снять','положить','перевод'
    }:
        return True
    return False


async def _hold_keyword_handler(m:Message):
    text=(m.text or '').strip()
    low=_hold_norm(text)
    p=low.split()
    uid=m.from_user.id
    db.user(uid,m.from_user.username,m.from_user.first_name)

    # Do not steal normal slash commands.
    if not low or low.startswith('/'):
        raise _HoldSkipHandler()

    # Multi-step bank operations: "снять goldcoin 1000" / "положить gold 1000".
    if len(p)==3 and p[0] in ('снять','положить') and p[1] in ('goldcoin','gold'):
        try:
            amount=Decimal(p[2].replace("'",'').replace(',','.'))
        except Exception:
            return await m.answer('❌ Количество должно быть положительным целым числом.')
        if amount<=0 or amount!=amount.to_integral_value():
            return await m.answer('❌ Количество должно быть положительным целым числом.')
        try:
            import bank_brand as _bank
            action='take' if p[0]=='снять' else 'put'
            cur='Goldcoin' if p[1]=='goldcoin' else 'gold'
            state[uid]={'bank':'amount','bank_action':action,'currency':cur}
            return await _bank.bank_state_input(m,sys.modules['__main__'])
        except Exception:
            logging.exception('bank keyword')
            state.pop(uid,None)
            return await m.answer('❌ Не удалось выполнить операцию с банком.')

    # Bank menu.
    if low=='банк':
        try:
            import bank_brand as _bank
            return await m.answer(_bank.bank_text(sys.modules['__main__'],uid),reply_markup=_bank.bank_menu(),parse_mode='HTML')
        except Exception:
            return await m.answer('❌ Банк временно недоступен.')

    # Simple sections / commands.
    simple={
        'б':lambda: m.answer(bal(uid),parse_mode='HTML'),
        'баланс':lambda: m.answer(bal(uid),parse_mode='HTML'),
        'профиль':lambda: m.answer(profile_text(uid),parse_mode='HTML',reply_markup=one_back('home')),
        'проф':lambda: m.answer(profile_text(uid),parse_mode='HTML',reply_markup=one_back('home')),
        'реф':lambda: m.answer(ref_text(uid),parse_mode='HTML',reply_markup=one_back('home')),
        'реферал':lambda: m.answer(ref_text(uid),parse_mode='HTML',reply_markup=one_back('home')),
        'рефералы':lambda: m.answer(ref_text(uid),parse_mode='HTML',reply_markup=one_back('home')),
        'топ':lambda: m.answer(top_text(),parse_mode='HTML',reply_markup=one_back('home')),
        'заработать':lambda: earn_open(m),
        'заработок':lambda: earn_open(m),
        'обменник':lambda: exchange_open(m),
        'обмен':lambda: exchange_open(m),
        'помощь':lambda: help_cmd(m),
        'хелп':lambda: help_cmd(m),
        'help':lambda: help_cmd(m),
        'правила':lambda: rules(m),
        'игры':lambda: m.answer(play_text(),reply_markup=play_k(),parse_mode='HTML'),
        'игра':lambda: m.answer(play_text(),reply_markup=play_k(),parse_mode='HTML'),
        'кейсы':lambda: cases(m),
        'кейс':lambda: cases(m),
        'бонус':lambda: bonus(m),
        'ежедневный':lambda: daily(m),
        'дейли':lambda: daily(m),
        'лотерея':lambda: lottery(m),
        'перевод':lambda: transfer(m),
        'донат':lambda: donate(m),
    }
    if low in simple:
        state.pop(uid,None)
        return await simple[low]()

    # Games with "name amount" syntax.
    aliases={
        'баскет':'basket','баскетбол':'basket','бск':'basket',
        'фтб':'football','футбол':'football',
        'дартс':'darts','дрс':'darts',
        'кубик':'dice','куб':'dice',
        'боулинг':'bowling','бол':'bowling',
        'сп':'spin','спин':'spin',
        'мины':'mines','мина':'mines',
        '21':'21','блэкджек':'21',
        'башня':'tower','монета':'coin','мон':'coin','кости':'dice2'
    }
    if len(p)>=2 and p[0] in aliases:
        try:
            amount=Decimal(p[1].replace("'",'').replace(',','.'))
        except Exception:
            return await m.answer('❌ Укажи корректную ставку, например: <b>баскет 500</b>',parse_mode='HTML')
        if amount<=0 or amount!=amount.to_integral_value():
            return await m.answer('❌ Ставка должна быть положительным целым числом.')
        game=aliases[p[0]]
        if db.balance(uid)[0] < amount:
            return await m.answer(f'❌ <b>Недостаточно {html.escape(currency_primary())}</b>\n\nБаланс: <b>{fmt(db.balance(uid)[0])} {html.escape(currency_primary())}</b>\nТребуется: <b>{fmt(amount)} {html.escape(currency_primary())}</b>',parse_mode='HTML')
        if game in ('basket','football','darts','bowling'):
            return await sports_game(m,game,amount)
        if game=='spin':
            return await spin_game(m,amount)
        labels={'mines':'💣 Мины','tower':'🗼 Башня','21':'🃏 21','coin':'🪙 Монета','dice':'🎲 Кубик','dice2':'🎲 Кости'}
        return await m.answer(f"{labels[game]}\n`{SEP}`\n\nВыбери вариант игры:",reply_markup=bet_k(game),parse_mode='HTML')

    # Unknown ordinary text must continue to the existing handlers.
    raise _HoldSkipHandler()


# Register first so it runs before generic text/state handlers.
_rh=_hold_keyword_handler
r.message.register(_rh,F.text)
if getattr(r.message,'handlers',None):
    _rec=r.message.handlers.pop()
    r.message.handlers.insert(0,_rec)
'''


def _run_bot_with_keywords():
    with open(BOT,'r',encoding='utf-8') as f:
        source=f.read()
    marker="if __name__=='__main__':asyncio.run(main())"
    if marker not in source:
        marker="if __name__ == '__main__':asyncio.run(main())"
    if marker not in source:
        raise RuntimeError('Cannot find bot.py polling marker')
    source=source.replace(marker,KEYWORDS+'\n'+marker,1)
    exec(compile(source,BOT,'exec'),globals(),globals())

while True:
    try:
        print('[BOT] Starting bot...',flush=True)
        _run_bot_with_keywords()
        print('[BOT] Process ended. Restarting in 3 seconds...',flush=True)
    except KeyboardInterrupt:
        print('[BOT] Stopped by user.',flush=True)
        break
    except SystemExit as e:
        print(f'[BOT] SystemExit: {e}. Restarting in 3 seconds...',flush=True)
    except Exception:
        print('[BOT] Unexpected crash. Full traceback:',flush=True)
        traceback.print_exc()
        print('[BOT] Restarting in 5 seconds...',flush=True)
        time.sleep(5)
    time.sleep(3)
