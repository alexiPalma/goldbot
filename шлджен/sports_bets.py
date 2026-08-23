"""Darts/bowling outcome betting extension."""
import asyncio
import sys
import time
from decimal import Decimal
from aiogram import F
from aiogram.utils.keyboard import InlineKeyboardBuilder
_INSTALLED=set(); _PENDING={}
DARTS={"miss":{1},"white":{2,4},"red":{3,5},"center":{6}}
BOWLING={"miss":{1},"pins1":{2},"pins2":{3},"pins3":{4},"pins4":{5},"strike":{6}}
ALIASES={"дартс":"darts","дрт":"darts","дарт":"darts","дртс":"darts","боулинг":"bowling","бл":"bowling","бол":"bowling"}
def a(): return sys.modules.get('__main__')
def fmt(x): return f"{Decimal(str(x)):,.0f}".replace(',','\'')
def cur(): return a().currency_primary()
def sep(): return getattr(a(),'SEP','·····················')
def labels(game):
    if game=='darts': return [('⚪ Белое','white'),('🔴 Красное','red'),('❌ Мимо','miss'),('🎯 Центр','center')]
    return [('💥 Страйк','strike'),('❌ Мимо','miss'),('1 кегля','pins1'),('2 кегли','pins2'),('3 кегли','pins3'),('4 кегли','pins4')]
def choice_k(uid,game,amount):
    b=InlineKeyboardBuilder()
    for text,ch in labels(game): b.button(text=text,callback_data=f'sportbet:{uid}:{game}:{ch}:{amount}')
    b.button(text='◀️ Назад',callback_data=f'sportback:{uid}:{game}'); b.adjust(2,2,2,1); return b.as_markup()
def bet_k(uid,game):
    b=InlineKeyboardBuilder()
    for n in (10,100,1000,10000,100000): b.button(text=fmt(n),callback_data=f'sportstart:{uid}:{game}:{n}')
    b.button(text='✍️ Своя ставка',callback_data=f'sportcustom:{uid}:{game}'); b.button(text='◀️ Назад',callback_data='play'); b.adjust(2,2,1,1,1); return b.as_markup()
async def show_start(target,game):
    title='🎯 <b>ДАРТС</b>' if game=='darts' else '🎳 <b>БОУЛИНГ</b>'
    return await a().show(target,f"{title}\n`{sep()}`\n\nВыбери ставку:",bet_k(target.from_user.id,game))
async def show_choice(target,game,amount):
    title='🎯 <b>ДАРТС</b>' if game=='darts' else '🎳 <b>БОУЛИНГ</b>'; prompt='Куда попадёт дартс?' if game=='darts' else 'Что угадываем?'
    return await a().show(target,f"{title}\n`{sep()}`\n\n{prompt}\n\n💰 Ставка: <b>{fmt(amount)} {cur()}</b>",choice_k(target.from_user.id,game,amount))
def parse_amount(s):
    try:
        x=Decimal(s.replace("'",'').replace(',',''))
        return x if x>0 and x==x.to_integral_value() else None
    except:return None
async def roll(c,uid,game,choice,amount):
    if c.from_user.id!=uid:return await c.answer()
    db=a().db; games=a().games
    if not games.cost(uid,amount,game+'_bet'): return await c.answer(f'❌ Недостаточно {cur()}.',show_alert=True)
    emoji='🎯' if game=='darts' else '🎳'
    try:
        msg=await a().bot.send_dice(c.message.chat.id,emoji=emoji); await asyncio.sleep(2); value=int(msg.dice.value)
    except Exception:
        db.add(uid,'Goldcoin',amount,game+'_refund'); return await c.answer('❌ Не удалось бросить. Ставка возвращена.',show_alert=True)
    mapping=DARTS if game=='darts' else BOWLING; win=value in mapping[choice]
    payout=amount*Decimal(db.setting('sport_multiplier') or '2') if win else Decimal(0)
    games.finish(uid,game,amount,f'{choice};roll:{value}',payout,win)
    actual=({1:'❌ Мимо',2:'⚪ Белое',3:'🔴 Красное',4:'⚪ Белое',5:'🔴 Красное',6:'🎯 Центр'} if game=='darts' else {1:'❌ Мимо',2:'1 кегля',3:'2 кегли',4:'3 кегли',5:'4 кегли',6:'💥 Страйк'})[value]
    chosen=dict(labels(game))[choice]; result=(f'🎉 <b>Победа!</b>\n💰 +{fmt(payout)} {cur()}' if win else f'❌ <b>Не угадал! Ставка −{fmt(amount)} {cur()}')
    text=f"{emoji} <b>{'ДАРТС' if game=='darts' else 'БОУЛИНГ'}</b>\n`{sep()}`\n\nТвой выбор: <b>{chosen}</b>\nВыпало: <b>{actual}</b>\n\n{result}\n\n{a().bal(uid)}"
    return await a().show(c,text,a().result_k(f'game:{game}'))
async def cb(c):
    d=c.data or ''; p=d.split(':'); uid=c.from_user.id
    if d.startswith('game:') and len(p)==2 and p[1] in ('darts','bowling'):
        await c.answer(); return await show_start(c,p[1])
    if d.startswith('bet:') and len(p)==3 and p[1] in ('darts','bowling'):
        amount=parse_amount(p[2]);
        if amount is None:return await c.answer('❌ Некорректная ставка.',show_alert=True)
        await c.answer(); return await show_choice(c,p[1],amount)
    if d.startswith('sportstart:') and len(p)==4:
        if uid!=int(p[1]):return await c.answer()
        await c.answer(); return await show_choice(c,p[2],Decimal(p[3]))
    if d.startswith('sportcustom:') and len(p)==3:
        if uid!=int(p[1]):return await c.answer()
        _PENDING[uid]=p[2]; await c.answer(); return await c.message.answer(f'✍️ Введи свою ставку для {"дартса" if p[2]=="darts" else "боулинга"}. Например: <code>30000</code>',parse_mode='HTML')
    if d.startswith('sportbet:') and len(p)==5:
        if uid!=int(p[1]):return await c.answer()
        await c.answer(); return await roll(c,uid,p[2],p[3],Decimal(p[4]))
    if d.startswith('sportback:') and len(p)==3:
        if uid!=int(p[1]):return await c.answer()
        await c.answer(); return await show_start(c,p[2])
def sport_callback_filter(c):
    d=c.data or ''
    return d.startswith(('game:darts','game:bowling','bet:darts:','bet:bowling:','sportstart:','sportcustom:','sportbet:','sportback:'))
async def msg_handler(message):
    text=(message.text or '').strip(); parts=text.lower().split(); uid=message.from_user.id
    if uid in _PENDING and text and not text.startswith('/'):
        game=_PENDING.pop(uid); amount=parse_amount(text)
        if amount is None:return await message.answer('❌ Ставка должна быть положительным целым числом.')
        return await show_choice(message,game,amount)
    if not parts or parts[0] not in ALIASES:return
    game=ALIASES[parts[0]]
    if len(parts)==1:return await show_start(message,game)
    if len(parts)==2:
        amount=parse_amount(parts[1])
        if amount is None:return await message.answer('❌ Укажи ставку числом, например: <code>дартс 100</code>',parse_mode='HTML')
        return await show_choice(message,game,amount)
def sport_message_filter(message):
    text=(message.text or '').strip().lower().split(); return message.from_user.id in _PENDING or bool(text and text[0] in ALIASES)
def patch_router():
    aa=a()
    if not aa or not hasattr(aa,'r'):return
    r=aa.r; key=id(r)
    if key in _INSTALLED:return
    r.callback_query.register(cb,sport_callback_filter)
    try:r.callback_query.handlers.insert(0,r.callback_query.handlers.pop())
    except:pass
    r.message.register(msg_handler,sport_message_filter)
    try:r.message.handlers.insert(0,r.message.handlers.pop())
    except:pass
    _INSTALLED.add(key); print('[EXT] Darts/bowling betting handlers ACTIVE.',flush=True)
def start():
    import threading
    def loop():
        while True:
            try:
                patch_router()
                aa=a()
                if aa is not None and hasattr(aa,'games'):
                    try:
                        import mines_tower_timeout
                        mines_tower_timeout.install(aa.games)
                    except Exception as e: print(f'[EXT] Mines/Tower timeout: {e}',flush=True)
            except Exception as e:print(f'[EXT] sports_bets: {e}',flush=True)
            time.sleep(.2)
    threading.Thread(target=loop,daemon=True,name='hold-sports-bets').start()
