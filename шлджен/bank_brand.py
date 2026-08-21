import sys, html, re
from decimal import Decimal, InvalidOperation
from aiogram import F
from aiogram.utils.keyboard import InlineKeyboardBuilder

SEP='·····················'

def app(): return sys.modules.get('__main__') or sys.modules.get('bot')

def cur_name(a, cur): return a.currency_primary() if cur == 'Goldcoin' else a.currency_premium()

def init_db(a):
    if not hasattr(a,'db') and hasattr(a,'DB'): a.db=a.DB
    a.db.c.execute('''CREATE TABLE IF NOT EXISTS bank_balances(uid INTEGER PRIMARY KEY,goldcoin TEXT NOT NULL DEFAULT '0',gold TEXT NOT NULL DEFAULT '0')''')
    a.db.set_setting('project_name','Holdgame')
    a.db.set_setting('primary_name','hCoin')
    a.db.set_setting('premium_name','HPOINT')
    a.db.set_setting('rate','45000')
    a.db.c.commit()

def ensure_bank_user(a,uid):
    a.db.user(uid); a.db.c.execute('INSERT OR IGNORE INTO bank_balances(uid,goldcoin,gold) VALUES(?,?,?)',(uid,'0','0')); a.db.c.commit()

def bank_bal(a,uid):
    ensure_bank_user(a,uid); r=a.db.c.execute('SELECT goldcoin,gold FROM bank_balances WHERE uid=?',(uid,)).fetchone(); return Decimal(str(r['goldcoin'])),Decimal(str(r['gold']))

def bank_text(a,uid):
    p,g=bank_bal(a,uid)
    return f'🏦 <b>HOLDGAME БАНК</b>\n`{SEP}`\n\n🏦 <b>Банковский баланс</b>\n💰 {a.fmt(p)} {html.escape(a.currency_primary())}\n🪙 {a.fmt(g)} {html.escape(a.currency_premium())}\n\n<b>Что вы хотите сделать?</b>'

def bank_menu():
    b=InlineKeyboardBuilder(); b.button(text='📥 Положить',callback_data='bank:put'); b.button(text='📤 Снять',callback_data='bank:take'); b.button(text='❌ Отмена',callback_data='bank:cancel'); b.adjust(2,1); return b.as_markup()

def currency_menu(action):
    b=InlineKeyboardBuilder(); b.button(text='💰 hCoin',callback_data=f'bank:currency:{action}:Goldcoin'); b.button(text='🪙 HPOINT',callback_data=f'bank:currency:{action}:gold'); b.button(text='❌ Отмена',callback_data='bank:cancel'); b.adjust(2,1); return b.as_markup()

def back_bank():
    b=InlineKeyboardBuilder(); b.button(text='❌ Отмена',callback_data='bank:cancel'); return b.as_markup()

async def bank_callback(c):
    a=app(); uid=c.from_user.id; d=c.data or ''
    if a is None:return False
    ensure_bank_user(a,uid)
    if d=='bank':
        await c.answer(); await c.message.edit_text(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return True
    if d=='bank:cancel':
        await c.answer(); a.state.pop(uid,None); await c.message.edit_text(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return True
    if d=='bank:put':
        await c.answer(); a.state[uid]={'bank':'currency','bank_action':'put'}; await c.message.edit_text('🏦 <b>ПОЛОЖИТЬ В БАНК</b>\n`'+SEP+'`\n\nКакая валюта?',reply_markup=currency_menu('put'),parse_mode='HTML'); return True
    if d=='bank:take':
        await c.answer(); a.state[uid]={'bank':'currency','bank_action':'take'}; await c.message.edit_text('🏦 <b>СНЯТЬ С БАНКА</b>\n`'+SEP+'`\n\nКакая валюта?',reply_markup=currency_menu('take'),parse_mode='HTML'); return True
    if d.startswith('bank:currency:'):
        await c.answer(); _,_,action,cur=d.split(':',3); a.state[uid]={'bank':'amount','bank_action':action,'currency':cur}; label=cur_name(a,cur)
        await c.message.edit_text(f'🏦 <b>{"ПОЛОЖИТЬ" if action=="put" else "СНЯТЬ"}</b>\n`{SEP}`\n\nСколько {html.escape(label)} вы хотите {"положить в банк" if action=="put" else "снять с банка"}?\n\nВведите целое число:',reply_markup=back_bank(),parse_mode='HTML'); return True
    return False

async def bank_state_input(m,a):
    uid=m.from_user.id; s=a.state.get(uid,{})
    if s.get('bank')!='amount': return False
    text=(m.text or '').strip().replace("'",'').replace(' ','')
    try: amount=Decimal(text)
    except (InvalidOperation,ValueError): await m.answer('❌ Введите положительное целое число.'); return True
    if amount<=0 or amount!=amount.to_integral_value(): await m.answer('❌ Введите положительное целое число.'); return True
    action=s.get('bank_action'); cur=s.get('currency'); col='goldcoin' if cur=='Goldcoin' else 'gold'; label=cur_name(a,cur); ensure_bank_user(a,uid)
    try:
        if action=='put':
            wallet=a.db.balance(uid)[0 if col=='goldcoin' else 1]
            if wallet<amount:
                await m.answer(f'❌ <b>Недостаточно {html.escape(label)}</b>.\n\nБаланс: <b>{a.fmt(wallet)} {html.escape(label)}</b>',parse_mode='HTML'); return True
            a.db.add(uid,cur,-amount,'bank_deposit')
            a.db.c.execute(f'UPDATE bank_balances SET {col}=CAST({col} AS REAL)+? WHERE uid=?',(str(amount),uid))
        else:
            bank_wallet=bank_bal(a,uid)[0 if col=='goldcoin' else 1]
            if bank_wallet<amount:
                await m.answer(f'❌ <b>В банке недостаточно {html.escape(label)}</b>.\n\nВ банке: <b>{a.fmt(bank_wallet)} {html.escape(label)}</b>',parse_mode='HTML'); return True
            a.db.c.execute(f'UPDATE bank_balances SET {col}=CAST({col} AS REAL)-? WHERE uid=?',(str(amount),uid))
            a.db.add(uid,cur,amount,'bank_withdraw')
        a.db.c.commit(); a.state.pop(uid,None)
        action_text='положено в банк' if action=='put' else 'снято с банка'
        await m.answer(f'✅ <b>Операция выполнена!</b>\n`{SEP}`\n\n{html.escape(label)}: <b>{a.fmt(amount)}</b>\nСумма {action_text}.\n\n{bank_text(a,uid)}',reply_markup=bank_menu(),parse_mode='HTML'); return True
    except Exception as e:
        a.db.c.rollback(); a.state.pop(uid,None)
        await m.answer(f'❌ <b>Операция не выполнена.</b>\n\nПричина: <code>{html.escape(str(e))}</code>',parse_mode='HTML'); return True

async def bank_message_handler(m):
    a=app(); uid=m.from_user.id; txt=(m.text or '').strip(); low=txt.lower(); parts=txt.split()
    if not txt or txt.startswith('/'): return False
    if s:=a.state.get(uid):
        if s.get('bank')=='amount': return await bank_state_input(m,a)
    if low=='банк':
        a.state.pop(uid,None); ensure_bank_user(a,uid); await m.answer(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return True
    if len(parts)==3 and parts[0].lower() in ('снять','положить') and parts[1].lower() in ('goldcoin','gold','hcoin','hpoint'):
        curraw=parts[1].lower(); cur='Goldcoin' if curraw in ('goldcoin','hcoin') else 'gold'
        a.state[uid]={'bank':'amount','bank_action':'take' if parts[0].lower()=='снять' else 'put','currency':cur}
        return await bank_state_input(m,a)
    return False

async def bank_command_handler(m):
    a=app(); uid=m.from_user.id; ensure_bank_user(a,uid); a.state.pop(uid,None); await m.answer(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML')

async def promo_message_handler(m):
    a=app(); uid=m.from_user.id; txt=(m.text or '').strip(); parts=txt.split(maxsplit=1)
    if not parts or parts[0].lower() not in ('промо','промокод'): return False
    if len(parts)==1:
        a.state[uid]={'promo':True}; await m.answer('🎟 <b>ПРОМОКОД</b>\n`'+SEP+'`\n\nВведи промокод:',parse_mode='HTML'); return True
    ok,msg=a.db.use_promo(uid,parts[1].strip()); a.state.pop(uid,None); await m.answer((f'🎉 <b>Промокод активирован!</b>\n`{SEP}`\n\n{msg}\n\n{a.bal(uid)}') if ok else '❌ '+msg,parse_mode='HTML'); return True

def patch_branding(a):
    for fn in ('home_text','top_text','help_main_text','profile_text'):
        old=getattr(a,fn,None)
        if not callable(old) or getattr(old,'_hold_brand',False): continue
        def make(oldfn,name):
            def w(*args,**kwargs):
                text=oldfn(*args,**kwargs)
                if not isinstance(text,str): return text
                text=text.replace('GOLDGAME','Holdgame').replace('GoldGame','Holdgame').replace('Goldgame','Holdgame').replace('Goldcoin','hCoin').replace('goldcoin','hCoin').replace('Gold','HPOINT') if name=='top_text' else text.replace('GOLDGAME','Holdgame').replace('GoldGame','Holdgame').replace('Goldgame','Holdgame')
                return text
            w._hold_brand=True; return w
        setattr(a,fn,make(old,fn))

def inject(a,dispatcher=None,original_include=None):
    init_db(a)
    if not hasattr(a,'r'): return
    # Register dedicated handlers first. This avoids relying on fragile handler wrapping/order.
    a.r.message.register(bank_message_handler,F.text)
    a.r.message.register(promo_message_handler,F.text)
    a.r.message.register(bank_command_handler,lambda m: bool((m.text or '').strip().lower().split('@',1)[0]=='/bank'))
    patch_branding(a)
