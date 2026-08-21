import sys, re, html
from decimal import Decimal, InvalidOperation
from aiogram import F
from aiogram.utils.keyboard import InlineKeyboardBuilder

SEP='·····················'

def app():
    return sys.modules.get('__main__') or sys.modules.get('bot')

def cur_name(a, cur):
    return a.currency_primary() if cur == 'Goldcoin' else a.currency_premium()

def init_db(a):
    if not hasattr(a, 'db') and hasattr(a, 'DB'):
        a.db = a.DB
    a.db.c.execute('''CREATE TABLE IF NOT EXISTS bank_balances(
        uid INTEGER PRIMARY KEY,
        goldcoin TEXT NOT NULL DEFAULT '0',
        gold TEXT NOT NULL DEFAULT '0'
    )''')
    # Project branding: use Holdgame everywhere the extension controls.
    a.db.set_setting('project_name', 'Holdgame')
    a.db.commit = getattr(a.db, 'commit', None)
    a.db.c.commit()

def ensure_bank_user(a, uid):
    a.db.user(uid)
    a.db.c.execute('INSERT OR IGNORE INTO bank_balances(uid,goldcoin,gold) VALUES(?,?,?)',(uid,'0','0'))
    a.db.c.commit()

def bank_bal(a, uid):
    ensure_bank_user(a, uid)
    r=a.db.c.execute('SELECT goldcoin,gold FROM bank_balances WHERE uid=?',(uid,)).fetchone()
    return Decimal(r['goldcoin']), Decimal(r['gold'])

def bank_text(a, uid):
    p,g=bank_bal(a,uid)
    return (
        f'🏦 <b>HOLDGAME БАНК</b>\n`{SEP}`\n\n'
        f'🏦 <b>Банковский баланс</b>\n'
        f'💰 {a.fmt(p)} {html.escape(a.currency_primary())}\n'
        f'🪙 {a.fmt(g)} {html.escape(a.currency_premium())}\n\n'
        f'Что вы хотите сделать?'
    )

def bank_menu():
    b=InlineKeyboardBuilder()
    b.button(text='📥 Положить',callback_data='bank:put')
    b.button(text='📤 Снять',callback_data='bank:take')
    b.button(text='❌ Отмена',callback_data='bank:cancel')
    b.adjust(2,1)
    return b.as_markup()

def currency_menu(action):
    b=InlineKeyboardBuilder()
    b.button(text='💰 Goldcoin',callback_data=f'bank:currency:{action}:Goldcoin')
    b.button(text='🪙 gold',callback_data=f'bank:currency:{action}:gold')
    b.button(text='❌ Отмена',callback_data='bank:cancel')
    b.adjust(2,1)
    return b.as_markup()

def back_bank():
    b=InlineKeyboardBuilder(); b.button(text='❌ Отмена',callback_data='bank:cancel'); return b.as_markup()

def open_bank(a, target, uid, edit=False):
    ensure_bank_user(a,uid)
    import asyncio
    text=bank_text(a,uid); markup=bank_menu()
    if edit:
        return target.message.edit_text(text,reply_markup=markup,parse_mode='HTML')
    return target.answer(text,reply_markup=markup,parse_mode='HTML')

async def bank_callback(c):
    a=app(); uid=c.from_user.id; d=c.data or ''
    if a is None:return False
    ensure_bank_user(a,uid)
    await c.answer()
    if d=='bank':
        await c.message.edit_text(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return True
    if d=='bank:cancel':
        a.state.pop(uid,None); await c.message.edit_text(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return True
    if d=='bank:put':
        a.state[uid]={'bank':'currency','bank_action':'put'}
        await c.message.edit_text('🏦 <b>ПОПОЛНЕНИЕ БАНКА</b>\n`'+SEP+'`\n\nКакая валюта?',reply_markup=currency_menu('put'),parse_mode='HTML'); return True
    if d=='bank:take':
        a.state[uid]={'bank':'currency','bank_action':'take'}
        await c.message.edit_text('🏦 <b>СНЯТИЕ С БАНКА</b>\n`'+SEP+'`\n\nКакая валюта?',reply_markup=currency_menu('take'),parse_mode='HTML'); return True
    if d.startswith('bank:currency:'):
        _,_,action,cur=d.split(':',3)
        a.state[uid]={'bank':'amount','bank_action':action,'currency':cur}
        label=cur_name(a,cur)
        await c.message.edit_text(f'🏦 <b>{"ПОЛОЖИТЬ" if action=="put" else "СНЯТЬ"}</b>\n`{SEP}`\n\nСколько {html.escape(label)} вы хотите {"положить в банк" if action=="put" else "снять с банка"}?\n\nВведите целое число:',reply_markup=back_bank(),parse_mode='HTML'); return True
    return False

def bank_state_input(m,a):
    uid=m.from_user.id; s=a.state.get(uid,{})
    if s.get('bank')!='amount': return False
    text=(m.text or '').strip().replace("'",'').replace(' ','')
    try: amount=Decimal(text)
    except InvalidOperation:
        return m.answer('❌ Введите положительное целое число.'), True
    if amount<=0 or amount!=amount.to_integral_value():
        return m.answer('❌ Введите положительное целое число.'), True
    action=s.get('bank_action'); cur=s.get('currency'); col='goldcoin' if cur=='Goldcoin' else 'gold'; label=cur_name(a,cur)
    ensure_bank_user(a,uid)
    if action=='put':
        wallet=a.db.balance(uid)[0 if col=='goldcoin' else 1]
        if wallet<amount:
            return m.answer(f'❌ Недостаточно {html.escape(label)}.\n\nБаланс: <b>{a.fmt(wallet)} {html.escape(label)}</b>',parse_mode='HTML'), True
        a.db.add(uid,cur,-amount,'bank_deposit')
        a.db.c.execute(f'UPDATE bank_balances SET {col}=CAST({col} AS REAL)+? WHERE uid=?',(str(amount),uid)); a.db.c.commit()
        a.state.pop(uid,None)
        return m.answer(f'✅ В банк положено: <b>{a.fmt(amount)} {html.escape(label)}</b>\n\n{bank_text(a,uid)}',reply_markup=bank_menu(),parse_mode='HTML'), True
    bank_wallet=bank_bal(a,uid)[0 if col=='goldcoin' else 1]
    if bank_wallet<amount:
        return m.answer(f'❌ В банке недостаточно {html.escape(label)}.\n\nВ банке: <b>{a.fmt(bank_wallet)} {html.escape(label)}</b>',parse_mode='HTML'), True
    a.db.c.execute(f'UPDATE bank_balances SET {col}=CAST({col} AS REAL)-? WHERE uid=?',(str(amount),uid)); a.db.c.commit()
    a.db.add(uid,cur,amount,'bank_withdraw')
    a.state.pop(uid,None)
    return m.answer(f'✅ Из банка снято: <b>{a.fmt(amount)} {html.escape(label)}</b>\n\n{bank_text(a,uid)}',reply_markup=bank_menu(),parse_mode='HTML'), True

def patch_main(a):
    old=a.main_k
    if getattr(old,'_hold_bank',False): return
    def wrapped(uid):
        markup=old(uid)
        for row in markup.inline_keyboard:
            if any(x.callback_data=='bank' for x in row): return markup
        b=InlineKeyboardBuilder()
        for row in markup.inline_keyboard: b.row(*row)
        b.button(text='🏦 Банк',callback_data='bank')
        b.adjust(2,2,2,2,2,2,2,2,1)
        return b.as_markup()
    wrapped._hold_bank=True
    a.main_k=wrapped

def patch_callback_router(a):
    # The main bot has a catch-all callback handler. Wrap that handler so bank
    # callbacks are processed before the catch-all handler can consume them.
    reg=a.r.callback_query
    for h in getattr(reg,'handlers',[]):
        cb=getattr(h,'callback',None)
        if getattr(cb,'__name__','')=='cb' and not getattr(cb,'_hold_bank_wrapped',False):
            original=cb
            async def wrapped(c):
                if (c.data or '').startswith('bank'):
                    if await bank_callback(c): return
                return await original(c)
            wrapped._hold_bank_wrapped=True
            h.callback=wrapped
            break

def patch_message_router(a):
    # Existing broad text handler can consume keywords first. Wrap it too.
    reg=a.r.message
    for h in getattr(reg,'handlers',[]):
        cb=getattr(h,'callback',None)
        name=getattr(cb,'__name__','')
        if name in ('group_keywords','state_input') and not getattr(cb,'_hold_bank_wrapped',False):
            original=cb
            async def wrapped(m):
                txt=(m.text or '').strip()
                low=txt.lower()
                # Explicit bank keyword always wins over an old dialog.
                if low=='банк':
                    a.state.pop(m.from_user.id,None)
                    return await m.answer(bank_text(a,m.from_user.id),reply_markup=bank_menu(),parse_mode='HTML')
                # Direct bank action: снять/положить currency amount.
                parts=txt.split()
                if len(parts)==3 and low.split()[0] in ('снять','положить') and parts[1].lower() in ('goldcoin','gold'):
                    action='take' if parts[0].lower()=='снять' else 'put'
                    a.state[m.from_user.id]={'bank':'amount','bank_action':action,'currency':'Goldcoin' if parts[1].lower()=='goldcoin' else 'gold'}
                    return (await bank_state_input(m,a))[0] if False else (await bank_state_input(m,a))
                if name=='state_input' and a.state.get(m.from_user.id,{}).get('bank')=='amount':
                    return await bank_state_input(m,a)
                return await original(m)
            wrapped._hold_bank_wrapped=True
            h.callback=wrapped
            break

def inject(a, dispatcher=None, original_include=None):
    init_db(a)
    if not hasattr(a,'r'): return
    ensure_bank_user(a,0) if False else None
    patch_main(a)
    patch_callback_router(a)
    patch_message_router(a)
