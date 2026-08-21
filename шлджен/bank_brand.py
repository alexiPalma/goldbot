import sys, html, re, asyncio
from decimal import Decimal, InvalidOperation
from aiogram import F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import BotCommand

SEP='·····················'
CHANNEL='@holdgamenews'
CHANNEL_URL='https://t.me/holdgamenews'

def app(): return sys.modules.get('__main__') or sys.modules.get('bot')
def cur_name(a,cur): return a.currency_primary() if cur=='Goldcoin' else a.currency_premium()

def init_db(a):
    if not hasattr(a,'db') and hasattr(a,'DB'): a.db=a.DB
    a.db.c.execute("CREATE TABLE IF NOT EXISTS bank_balances(uid INTEGER PRIMARY KEY,goldcoin TEXT NOT NULL DEFAULT '0',gold TEXT NOT NULL DEFAULT '0')")
    a.db.set_setting('project_name','Holdgame'); a.db.set_setting('primary_name','hCoin'); a.db.set_setting('premium_name','HPOINT'); a.db.set_setting('rate','45000'); a.db.c.commit()

def ensure_bank_user(a,uid):
    a.db.user(uid); a.db.c.execute("INSERT OR IGNORE INTO bank_balances(uid,goldcoin,gold) VALUES(?,?,?)",(uid,'0','0')); a.db.c.commit()

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

def sub_keyboard():
    b=InlineKeyboardBuilder(); b.button(text='📢 Подписаться на канал',url=CHANNEL_URL); b.button(text='✅ Проверить подписку',callback_data='subscription:check'); b.adjust(1,1); return b.as_markup()
def sub_text():
    return f'🔐 <b>ДОСТУП К HOLDGAME</b>\n`{SEP}`\n\nЧтобы пользоваться ботом, сначала подпишись на наш канал.\n\n📢 <b>Канал:</b> @holdgamenews\n\nПосле подписки нажми кнопку <b>«Проверить подписку»</b>.'

async def is_subscribed(a,uid):
    try:
        member=await a.bot.get_chat_member(CHANNEL,uid)
        return member.status in ('creator','administrator','member') or (member.status=='restricted' and getattr(member,'is_member',False))
    except Exception:
        return False

async def subscription_message_guard(m):
    a=app()
    if a is None or not getattr(m,'from_user',None): raise SkipHandler()
    text=(m.text or '').strip()
    if text.lower().split('@',1)[0]=='/start':
        if not await is_subscribed(a,m.from_user.id): await m.answer(sub_text(),reply_markup=sub_keyboard(),parse_mode='HTML'); return
        raise SkipHandler()
    if not await is_subscribed(a,m.from_user.id): await m.answer(sub_text(),reply_markup=sub_keyboard(),parse_mode='HTML'); return
    raise SkipHandler()

async def subscription_callback_guard(c):
    a=app()
    if a is None: raise SkipHandler()
    if c.data=='subscription:check':
        if await is_subscribed(a,c.from_user.id):
            await c.answer('✅ Подписка подтверждена!',show_alert=True)
            try: await c.message.edit_text(a.home_text(c.from_user.id),reply_markup=a.main_k(c.from_user.id),parse_mode='HTML')
            except Exception: await c.message.answer(a.home_text(c.from_user.id),reply_markup=a.main_k(c.from_user.id),parse_mode='HTML')
        else: await c.answer('❌ Ты ещё не подписался на канал.',show_alert=True)
        return
    if not await is_subscribed(a,c.from_user.id): await c.answer('❌ Сначала подпишись на @holdgamenews.',show_alert=True); return
    raise SkipHandler()

async def bank_callback(c):
    a=app(); uid=c.from_user.id; d=c.data or ''
    if a is None:return
    if not await is_subscribed(a,uid): await c.answer('❌ Сначала подпишись на @holdgamenews.',show_alert=True); return
    ensure_bank_user(a,uid)
    try:
        if d=='bank': await c.answer(); await c.message.edit_text(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return
        if d=='bank:cancel': await c.answer(); a.state.pop(uid,None); await c.message.edit_text(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return
        if d=='bank:put': await c.answer(); a.state[uid]={'bank':'currency','bank_action':'put'}; await c.message.edit_text('🏦 <b>ПОЛОЖИТЬ В БАНК</b>\n`'+SEP+'`\n\nКакая валюта?',reply_markup=currency_menu('put'),parse_mode='HTML'); return
        if d=='bank:take': await c.answer(); a.state[uid]={'bank':'currency','bank_action':'take'}; await c.message.edit_text('🏦 <b>СНЯТЬ С БАНКА</b>\n`'+SEP+'`\n\nКакая валюта?',reply_markup=currency_menu('take'),parse_mode='HTML'); return
        if d.startswith('bank:currency:'):
            await c.answer(); _,_,action,cur=d.split(':',3); a.state[uid]={'bank':'amount','bank_action':action,'currency':cur}; label=cur_name(a,cur)
            await c.message.edit_text(f'🏦 <b>{"ПОЛОЖИТЬ" if action=="put" else "СНЯТЬ"}</b>\n`{SEP}`\n\nСколько {html.escape(label)} вы хотите {"положить в банк" if action=="put" else "снять с банка"}?\n\nВведите целое число:',reply_markup=back_bank(),parse_mode='HTML'); return
    except Exception as e:
        await c.answer('❌ Ошибка банка. Проверь консоль.',show_alert=True)
        print('[BANK CALLBACK ERROR]',repr(e),flush=True)

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
            if wallet<amount: await m.answer(f'❌ <b>Недостаточно {html.escape(label)}</b>.\n\nБаланс: <b>{a.fmt(wallet)} {html.escape(label)}</b>',parse_mode='HTML'); return True
            a.db.add(uid,cur,-amount,'bank_deposit'); a.db.c.execute(f'UPDATE bank_balances SET {col}=CAST({col} AS REAL)+? WHERE uid=?',(str(amount),uid))
        else:
            bank_wallet=bank_bal(a,uid)[0 if col=='goldcoin' else 1]
            if bank_wallet<amount: await m.answer(f'❌ <b>В банке недостаточно {html.escape(label)}</b>.\n\nВ банке: <b>{a.fmt(bank_wallet)} {html.escape(label)}</b>',parse_mode='HTML'); return True
            a.db.c.execute(f'UPDATE bank_balances SET {col}=CAST({col} AS REAL)-? WHERE uid=?',(str(amount),uid)); a.db.add(uid,cur,amount,'bank_withdraw')
        a.db.c.commit(); a.state.pop(uid,None); action_text='положено в банк' if action=='put' else 'снято с банка'
        await m.answer(f'✅ <b>Операция выполнена!</b>\n`{SEP}`\n\n{html.escape(label)}: <b>{a.fmt(amount)}</b>\nСумма {action_text}.\n\n{bank_text(a,uid)}',reply_markup=bank_menu(),parse_mode='HTML'); return True
    except Exception as e:
        a.db.c.rollback(); a.state.pop(uid,None); await m.answer(f'❌ <b>Операция не выполнена.</b>\n\nПричина: <code>{html.escape(str(e))}</code>',parse_mode='HTML'); return True

async def bank_message_handler(m):
    a=app(); uid=m.from_user.id; txt=(m.text or '').strip(); low=txt.lower()
    if not txt or txt.startswith('/'): raise SkipHandler()
    if (s:=a.state.get(uid)) and s.get('bank') in ('amount','currency'):
        if s.get('bank')=='amount': return await bank_state_input(m,a)
        raise SkipHandler()
    if low=='банк':
        a.state.pop(uid,None); ensure_bank_user(a,uid); await m.answer(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML'); return
    raise SkipHandler()

async def bank_command_handler(m):
    a=app(); uid=m.from_user.id; ensure_bank_user(a,uid); a.state.pop(uid,None); await m.answer(bank_text(a,uid),reply_markup=bank_menu(),parse_mode='HTML')

def patch_branding(a):
    old_main=getattr(a,'main_k',None)
    if callable(old_main) and not getattr(old_main,'_hold_bank_brand',False):
        def main_wrap(uid):
            kb=old_main(uid)
            try:
                rows=list(kb.inline_keyboard)
                rows=[list(row) for row in rows]
                if not any(any(getattr(btn,'callback_data',None)=='bank' for btn in row) for row in rows):
                    from aiogram.types import InlineKeyboardButton
                    rows.insert(0,[InlineKeyboardButton(text='🏦 Банк',callback_data='bank')])
                kb.inline_keyboard=rows
            except Exception as e: print('[BANK MENU ERROR]',repr(e),flush=True)
            return kb
        main_wrap._hold_bank_brand=True; a.main_k=main_wrap
    # Telegram command menu is set by bot.py after injection, so wrap set_my_commands
    old_set=getattr(a.bot,'set_my_commands',None)
    if callable(old_set) and not getattr(old_set,'_hold_bank_commands',False):
        async def set_commands(commands,*args,**kwargs):
            commands=list(commands or [])
            if not any(getattr(x,'command',None)=='bank' for x in commands): commands.append(BotCommand(command='bank',description='🏦 Банк'))
            return await old_set(commands,*args,**kwargs)
        set_commands._hold_bank_commands=True; a.bot.set_my_commands=set_commands

def inject(a,dispatcher=None,original_include=None):
    init_db(a)
    if not hasattr(a,'r'): return
    patch_branding(a)
    # Bank handlers must be ahead of the universal keyword/owner handlers.
    a.r.callback_query.register(bank_callback,F.data.startswith('bank:') | (F.data=='bank'),index=0)
    a.r.message.register(bank_command_handler,Command('bank'),index=0)
    a.r.message.register(bank_message_handler,F.text,index=0)
    # Subscription check comes after the bank handlers so bank UI cannot be swallowed.
    a.r.callback_query.register(subscription_callback_guard,F.data.startswith('subscription:'),index=0)
    a.r.message.register(subscription_message_guard,F.text,index=0)
    print('[EXT] Holdgame bank: command + menu + callbacks installed with priority.',flush=True)
