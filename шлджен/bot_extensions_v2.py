import asyncio
import sys
import time
import random
from decimal import Decimal
from aiogram import F
from aiogram.utils.keyboard import InlineKeyboardBuilder

_INSTALLED = False
_DUELS = {}

ALIASES = {
    'basket': {'бск', 'баскетбол', 'баскет'},
    'football': {'фтб', 'футбол'},
    'darts': {'дрт', 'дартс'},
    'dice': {'куб', 'кубик'},
    'bowling': {'бл', 'бол', 'боулинг'},
    'spin': {'сп', 'спин'},
    'mines': {'мины', 'мина'},
    '21': {'21', 'очко', '21очко'},
    'tower': {'башня', 'баш'},
    'coin': {'монета', 'мон'},
    'dice2': {'кости', 'кст', 'кост'},
}
ALIAS_TO_GAME = {a: g for g, xs in ALIASES.items() for a in xs}
LABELS = {'basket':'🏀 Баскетбол','football':'⚽ Футбол','darts':'🎯 Дартс','dice':'🎲 Кубик','bowling':'🎳 Боулинг','spin':'🎰 Спин','mines':'💣 Мины','21':'🃏 21 очко','tower':'🗼 Башня','coin':'🪙 Монета','dice2':'🎲 Кости'}

def _ctx(): return sys.modules['__main__']
def _fmt(x): return f"{Decimal(str(x)):,.0f}".replace(',',"'")
def _cur(a): return a.currency_primary()
def _sep(a): return getattr(a,'SEP','·····················')
def _ok(c,uid): return c.from_user.id==int(uid)
def _cb(uid,action,*p): return ':'.join(['gx',str(uid),action,*map(str,p)])

def _games_k(uid):
    b=InlineKeyboardBuilder()
    for g in LABELS:b.button(text=LABELS[g],callback_data=_cb(uid,'game',g))
    b.button(text='🏠 Главное меню',callback_data=_cb(uid,'home')); b.adjust(2,2,2,2,2,2,1); return b.as_markup()

def _bet_k(uid,game):
    b=InlineKeyboardBuilder()
    for n in (10,100,1000,10000,100000): b.button(text=_fmt(n),callback_data=_cb(uid,'bet',game,n))
    b.button(text='✍️ Своя ставка',callback_data=_cb(uid,'custom',game)); b.button(text='◀️ Назад',callback_data=_cb(uid,'play')); b.adjust(2,2,1,1,1); return b.as_markup()

def _dice_k(uid,amount):
    b=InlineKeyboardBuilder()
    for n in range(1,7): b.button(text=str(n),callback_data=_cb(uid,'dicepick',n,amount))
    b.button(text='◀️ Назад',callback_data=_cb(uid,'game','dice')); b.adjust(3,3,1); return b.as_markup()

def _dice2_k(uid,amount):
    b=InlineKeyboardBuilder()
    for n in range(2,6):
        b.button(text=f'Меньше {n}',callback_data=_cb(uid,'dicecond','lt',n,amount)); b.button(text=f'Равно {n}',callback_data=_cb(uid,'dicecond','eq',n,amount)); b.button(text=f'Больше {n}',callback_data=_cb(uid,'dicecond','gt',n,amount))
    b.button(text='◀️ Назад',callback_data=_cb(uid,'game','dice2')); b.adjust(3,3,3,3,1); return b.as_markup()

def _coin_k(uid,amount):
    b=InlineKeyboardBuilder(); b.button(text='🦅 Орёл',callback_data=_cb(uid,'coin','Орёл',amount)); b.button(text='🪙 Решка',callback_data=_cb(uid,'coin','Решка',amount)); b.button(text='◀️ Назад',callback_data=_cb(uid,'game','coin')); b.adjust(2,1); return b.as_markup()

async def _show(target,text,markup=None): return await _ctx().show(target,text,markup)

async def _start_bet(uid,game,amount,chat_id,message):
    a=_ctx(); db,games,bot=a.db,a.games,a.bot; amount=Decimal(str(amount))
    if amount<=0 or amount!=amount.to_integral_value(): return await message.answer('⚠️ Введи положительное целое число.')
    if db.balance(uid)[0]<amount: return await message.answer(f"❌ Недостаточно {_cur(a)}.",parse_mode='HTML')
    if game=='mines':
        if not games.mines_start(uid,amount): return await message.answer('❌ Игра уже идёт или ставка недоступна.')
        return await _show(message,f"💣 <b>МИНЫ</b>\n`{_sep(a)}`\n\n💰 Ставка: <b>{_fmt(amount)} {_cur(a)}</b>\n💣 Мин: <b>3</b>\n\nОткрывай клетки. Бомба заканчивает игру.",a.mines_k(games.mines[uid]))
    if game=='tower':
        if not games.tower_start(uid,amount): return await message.answer('❌ Игра уже идёт или ставка недоступна.')
        return await _show(message,f"🗼 <b>БАШНЯ</b>\n`{_sep(a)}`\n\n💰 Ставка: <b>{_fmt(amount)} {_cur(a)}</b>\n📍 Высота: <b>1 / 6</b>",a.tower_k())
    if game=='21':
        g=games.blackjack_start(uid,amount)
        if not g:return await message.answer('❌ Не удалось начать игру.')
        return await _show(message,a.bj_text(g,hide=True),a.bj_k())
    if game=='dice': return await _show(message,f"🎲 <b>КУБИК</b>\n`{_sep(a)}`\n\nЗагадай число от <b>1 до 6</b>.\n\nСтавка: <b>{_fmt(amount)} {_cur(a)}</b>",_dice_k(uid,amount))
    if game=='dice2': return await _show(message,f"🎲 <b>КОСТИ</b>\n`{_sep(a)}`\n\nВыбери условие и число <b>от 2 до 5</b>:",_dice2_k(uid,amount))
    if game=='coin': return await _show(message,f"🪙 <b>МОНЕТА</b>\n`{_sep(a)}`\n\nВыбери сторону.\n\nСтавка: <b>{_fmt(amount)} {_cur(a)}</b>",_coin_k(uid,amount))
    if game in ('basket','football','darts','bowling'):
        emoji={'basket':'🏀','football':'⚽','darts':'🎯','bowling':'🎳'}[game]; label=LABELS[game]
        if not games.cost(uid,amount,game+'_bet'):return await message.answer(f'❌ Недостаточно {_cur(a)}.')
        msg=await bot.send_dice(chat_id,emoji=emoji); await asyncio.sleep(2); v=msg.dice.value
        win=v in {'basket':{4,5},'football':{3,4,5},'darts':{6},'bowling':{6}}[game]; payout=amount*Decimal(db.setting('sport_multiplier') or '2') if win else Decimal(0)
        games.finish(uid,game,amount,'hit' if win else 'miss',payout,win)
        text=f"{emoji} <b>{label}</b>\n`{_sep(a)}`\n\nВыпало: <b>{v}</b>\n\n"+(f"🎯 <b>Победа!</b>\n💰 +{_fmt(payout)} {_cur(a)}" if win else f"❌ <b>Мимо!</b>\n💸 −{_fmt(amount)} {_cur(a)}")+f"\n\n{a.bal(uid)}"
        return await bot.send_message(chat_id,text,parse_mode='HTML',reply_markup=a.result_k(f'game:{game}'))
    if game=='spin':
        if not games.cost(uid,amount,'spin_bet'):return await message.answer(f'❌ Недостаточно {_cur(a)}.')
        msg=await bot.send_dice(chat_id,emoji='🎰'); await asyncio.sleep(2.2); v=int(msg.dice.value)
        if v==64: reels=['7️⃣','7️⃣','7️⃣']
        else:
            mapping=[1,2,3,0]; symbols=['🍒','🍋','🔔','7️⃣']; digits=[mapping[(v-1)&3],mapping[((v-1)>>2)&3],mapping[((v-1)>>4)&3]]; reels=[symbols[d] for d in digits]
        win=len(set(reels))==1; payout=amount*Decimal(db.setting('spin_multiplier') or '5') if win else Decimal(0); games.finish(uid,'spin',amount,'|'.join(reels),payout,win)
        text=f"🎰 <b>СПИН</b>\n`{_sep(a)}`\n\n"+('🎉 <b>ТРИ ОДИНАКОВЫХ!</b>' if win else '😔 <b>Комбинация не собрана.</b>')+"\n"+(f"💰 +{_fmt(payout)} {_cur(a)}" if win else f"💸 −{_fmt(amount)} {_cur(a)}")+f"\n\n{a.bal(uid)}"
        return await bot.send_message(chat_id,text,parse_mode='HTML',reply_markup=a.result_k('game:spin'))

async def _dicepick(c,uid,guess,amount):
    a=_ctx(); db,games,bot=a.db,a.games,a.bot; amount=Decimal(str(amount))
    if db.balance(uid)[0]<amount or not db.add(uid,'Goldcoin',-amount,'dice_bet'):return await c.answer('❌ Недостаточно средств.',show_alert=True)
    msg=await bot.send_dice(c.message.chat.id,emoji='🎲'); await asyncio.sleep(2); v=msg.dice.value; win=v==guess; payout=amount*Decimal(db.setting('dice_multiplier') or '6') if win else Decimal(0); games.finish(uid,'dice',amount,f'guess:{guess};roll:{v}',payout,win)
    return await _show(c,f"🎲 <b>КУБИК</b>\n`{_sep(a)}`\n\nЗагадано: <b>{guess}</b>\nВыпало: <b>{v}</b>\n\n"+(f"🎉 <b>ПОПАЛ!</b>\n+{_fmt(payout)} {_cur(a)}" if win else '❌ <b>МИМО!</b>'),a.result_k('game:dice'))

async def _dicecond(c,uid,op,target,amount):
    a=_ctx(); db,games,bot=a.db,a.games,a.bot; target=int(target); amount=Decimal(str(amount))
    if target<2 or target>5:return await c.answer('❌ Доступны числа только от 2 до 5.',show_alert=True)
    if db.balance(uid)[0]<amount or not db.add(uid,'Goldcoin',-amount,'dice2_bet'):return await c.answer('❌ Недостаточно средств.',show_alert=True)
    msg=await bot.send_dice(c.message.chat.id,emoji='🎲'); await asyncio.sleep(2); v=msg.dice.value; win={'lt':v<target,'eq':v==target,'gt':v>target}[op]; payout=amount*Decimal('1.8') if win else Decimal(0); games.finish(uid,'dice2',amount,f'{op}:{target};roll:{v}',payout,win); words={'lt':'меньше','eq':'равно','gt':'больше'}
    return await _show(c,f"🎲 <b>КОСТИ</b>\n`{_sep(a)}`\n\nУсловие: <b>{words[op]} {target}</b>\nВыпало: <b>{v}</b>\n\n"+(f"🎉 <b>Условие выполнено!</b>\n+{_fmt(payout)} {_cur(a)}" if win else '❌ <b>Условие не выполнено.</b>'),a.result_k('game:dice2'))

async def _coin(c,uid,choice,amount):
    a=_ctx(); db,games=a.db,a.games; amount=Decimal(str(amount))
    if db.balance(uid)[0]<amount or not db.add(uid,'Goldcoin',-amount,'coin_bet'):return await c.answer('❌ Недостаточно средств.',show_alert=True)
    anim=await c.message.answer('🪙')
    for frame in ('🪙','🦅','🪙','🦅','🪙'):
        await asyncio.sleep(.35)
        try: await anim.edit_text(frame)
        except Exception: pass
    v=random.choice(['Орёл','Решка']); win=v==choice; payout=amount*2 if win else Decimal(0); games.finish(uid,'coin',amount,v,payout,win)
    return await anim.edit_text(f"🪙 <b>МОНЕТА</b>\n`{_sep(a)}`\n\nВыпало: <b>{v}</b>\n\n"+(f"🎉 <b>Ты угадал!</b>\n💰 +{_fmt(payout)} {_cur(a)}" if win else f"❌ <b>Не угадал!</b>\n💸 −{_fmt(amount)} {_cur(a)}")+f"\n\n{a.bal(uid)}",parse_mode='HTML',reply_markup=a.result_k('game:coin'))

async def _invite(duel,player):
    a=_ctx(); uid=duel[player]; opp=duel['b'] if player=='a' else duel['a']; intro=f"Ты вызываешь {a.uname(opp)} на дуэль." if player=='a' else f"{a.uname(opp)} вызывает тебя на дуэль."
    text=f"🎲 <b>ДУЭЛЬ</b>\n`{_sep(a)}`\n\n{intro}\nСтавка: <b>{_fmt(duel['bet'])} {_cur(a)}</b>\n\nГотов участвовать?"
    kb=InlineKeyboardBuilder(); kb.button(text='✅ Готов',callback_data=f"duel:{duel['id']}:{uid}:ready"); kb.button(text='❌ Нет',callback_data=f"duel:{duel['id']}:{uid}:no"); kb.adjust(2)
    return await a.bot.send_message(uid,text,parse_mode='HTML',reply_markup=kb.as_markup())

async def _finish_duel(duel):
    a=_ctx(); db,bot=a.db,a.bot; av,bv=duel['rolls']['a'],duel['rolls']['b']
    if av==bv:
        db.add(duel['a'],'Goldcoin',duel['bet'],'duel_refund'); db.add(duel['b'],'Goldcoin',duel['bet'],'duel_refund'); text=f"🤝 <b>НИЧЬЯ</b> — оба выбросили <b>{av}</b>. Ставки возвращены."
    else:
        w='a' if av>bv else 'b'; db.add(duel[w],'Goldcoin',duel['bet']*2,'duel_win'); text=f"🏆 <b>ПОБЕДИТЕЛЬ: {a.uname(duel[w])}</b>\n\n🎲 {a.uname(duel['a'])}: <b>{av}</b>\n🎲 {a.uname(duel['b'])}: <b>{bv}</b>\n\n💰 Победитель получает <b>{_fmt(duel['bet']*2)} {_cur(a)}</b>."
    try: await bot.send_message(duel['chat_id'],text,parse_mode='HTML')
    except Exception: pass
    for uid in (duel['a'],duel['b']):
        if uid==duel['chat_id']: continue
        try: await bot.send_message(uid,text,parse_mode='HTML')
        except Exception: pass
    _DUELS.pop(duel['id'],None)

async def _roll_duel(duel,player):
    a=_ctx(); uid=duel[player]
    try:
        msg=await a.bot.send_dice(duel['chat_id'],emoji='🎲'); await asyncio.sleep(2); v=msg.dice.value
    except Exception:
        v=random.randint(1,6)
        try: await a.bot.send_message(duel['chat_id'],f"🎲 Выпало: <b>{v}</b>",parse_mode='HTML')
        except Exception: pass
    duel['rolls'][player]=v
    if len(duel['rolls'])==2:return await _finish_duel(duel)
    nxt='b' if player=='a' else 'a'
    try: await a.bot.send_message(duel['chat_id'],f"🎲 {a.uname(uid)} выбросил <b>{v}</b>.\nСледующий бросок — {a.uname(duel[nxt])}.",parse_mode='HTML')
    except Exception: pass
    await _roll_duel(duel,nxt)

async def _ready(duel,uid):
    if duel.get('finished') or uid not in (duel['a'],duel['b']):return
    duel['ready']['a' if uid==duel['a'] else 'b']=True
    if not all(duel['ready'].values()):
        try: await _ctx().bot.send_message(uid,'✅ Готовность отмечена. Ждём второго игрока.')
        except Exception: pass
        return
    if duel.get('started'):return
    duel['started']=True; a=_ctx(); db=a.db
    if db.balance(duel['a'])[0]<duel['bet'] or db.balance(duel['b'])[0]<duel['bet']:
        duel['finished']=True; _DUELS.pop(duel['id'],None)
        try: await a.bot.send_message(duel['chat_id'],'❌ У одного из игроков недостаточно средств. Дуэль отменена.')
        except Exception: pass
        return
    first=db.add(duel['a'],'Goldcoin',-duel['bet'],'duel_bet'); second=db.add(duel['b'],'Goldcoin',-duel['bet'],'duel_bet')
    if not first or not second:
        if first:db.add(duel['a'],'Goldcoin',duel['bet'],'duel_rollback')
        if second:db.add(duel['b'],'Goldcoin',duel['bet'],'duel_rollback')
        duel['finished']=True; _DUELS.pop(duel['id'],None); return
    try: await a.bot.send_message(duel['chat_id'],f"🎲 <b>ДУЭЛЬ НАЧИНАЕТСЯ</b>\n`{_sep(a)}`\n\nПервым бросает {a.uname(duel['a'])}.",parse_mode='HTML')
    except Exception: pass
    await _roll_duel(duel,'a')

async def _no(duel,uid):
    if duel.get('finished') or uid not in (duel['a'],duel['b']):return
    duel['finished']=True; _DUELS.pop(duel['id'],None); a=_ctx()
    try: await a.bot.send_message(duel['chat_id'],f"❌ <b>ДУЭЛЬ ОТМЕНЕНА</b>\n\n{a.uname(uid)} отказался от участия.",parse_mode='HTML')
    except Exception: pass

async def _callback(c):
    d=c.data or ''; a=_ctx()
    if d.startswith('gx:'):
        p=d.split(':')
        if len(p)<3 or not _ok(c,p[1]):return await c.answer()
        uid=int(p[1]); action=p[2]; await c.answer()
        if action=='home':return await _show(c,a.home_text(uid),a.main_k(uid))
        if action=='play':return await _show(c,a.play_text(),_games_k(uid))
        if action=='game':
            game=p[3]; return await _show(c,f"{LABELS.get(game,'🎮 Игра')}\n`{_sep(a)}`\n\nВыбери ставку:",_bet_k(uid,game))
        if action=='custom':
            game=p[3]; a.state[uid]={'custom_bet':game}; return await _show(c,f"✍️ <b>СВОЯ СТАВКА</b>\n`{_sep(a)}`\n\nВведи сумму ставки для {LABELS.get(game,'игры')} одним сообщением.",a.one_back('play'))
        if action=='bet':return await _start_bet(uid,p[3],Decimal(p[4]),c.message.chat.id,c.message)
        if action=='dicepick':return await _dicepick(c,uid,int(p[3]),Decimal(p[4]))
        if action=='dicecond':return await _dicecond(c,uid,p[3],int(p[4]),Decimal(p[5]))
        if action=='coin':return await _coin(c,uid,p[3],Decimal(p[4]))
    if d.startswith('duel:'):
        p=d.split(':')
        if len(p)!=4 or not _ok(c,p[2]):return await c.answer()
        await c.answer(); duel=_DUELS.get(p[1])
        if not duel:return
        if p[3]=='ready':return await _ready(duel,int(p[2]))
        if p[3]=='no':return await _no(duel,int(p[2]))
    if d.startswith('dicecond:'):
        try:
            target=int(d.split(':')[2])
            if target<2 or target>5:return await c.answer('❌ Доступны числа только от 2 до 5.',show_alert=True)
        except Exception:return await c.answer('❌ Некорректное условие.',show_alert=True)

async def _message(m):
    a=_ctx(); uid=m.from_user.id; text=(m.text or '').strip(); a.db.user(uid,m.from_user.username,m.from_user.first_name)
    if text.startswith('/'):return
    s=a.state.get(uid,{})
    if s.get('custom_bet'):
        try:amount=Decimal(text)
        except Exception:a.state.pop(uid,None);return
        if amount<=0 or amount!=amount.to_integral_value():a.state.pop(uid,None);return
        game=s['custom_bet'];a.state.pop(uid,None);return await _start_bet(uid,game,amount,m.chat.id,m)
    parts=text.split()
    if parts and parts[0].lower() in ('дуэль','дуель','duel'):
        if len(parts)!=3:return await m.answer('⚠️ Формат: <code>дуэль 100 @username</code>',parse_mode='HTML')
        try:bet=Decimal(parts[1])
        except Exception:return await m.answer('⚠️ Ставка должна быть положительным целым числом.')
        if bet<=0 or bet!=bet.to_integral_value():return await m.answer('⚠️ Ставка должна быть положительным целым числом.')
        target=a.db.find(parts[2])
        if not target:return await m.answer('❌ Пользователь не найден. Он должен хотя бы один раз открыть бота.')
        if target['id']==uid:return await m.answer('❌ Нельзя вызвать самого себя.')
        if a.db.balance(uid)[0]<bet:return await m.answer(f'❌ Недостаточно {_cur(a)} для ставки {_fmt(bet)}.')
        did=f"{uid}_{target['id']}_{int(time.time()*1000)}"; duel={'id':did,'a':uid,'b':target['id'],'bet':bet,'chat_id':m.chat.id,'ready':{'a':False,'b':False},'rolls':{},'started':False,'finished':False};_DUELS[did]=duel
        await _invite(duel,'a');await _invite(duel,'b')
        return await m.answer(f"🎲 Приглашение на дуэль отправлено {a.uname(target['id'])}.\nСтавка: <b>{_fmt(bet)} {_cur(a)}</b>.",parse_mode='HTML')
    first=parts[0].lower() if parts else '';game=ALIAS_TO_GAME.get(first)
    if game:
        if len(parts)==1:return await _show(m,f"{LABELS[game]}\n`{_sep(a)}`\n\nВыбери ставку:",_bet_k(uid,game))
        if len(parts)==2:
            try:amount=Decimal(parts[1])
            except Exception:return
            if amount<=0 or amount!=amount.to_integral_value():return
            return await _start_bet(uid,game,amount,m.chat.id,m)
        return
    if s.get('admin') in {'earn','admins','money','broadcast','stats'}:a.state.pop(uid,None)


def install(db):
    global _INSTALLED
    if _INSTALLED:return
    a=_ctx();r=a.r
    r.callback_query.register(_callback,F.data.startswith('gx:') | F.data.startswith('duel:') | F.data.startswith('dicecond:'))
    r.message.register(_message,F.text & ~F.text.startswith('/'))
    _INSTALLED=True
