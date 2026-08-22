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
    except Exception: return False

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
    if a is None: return
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
        await c.answer('❌ Ошибка банка. Проверь консоль.',show_alert=True); print('[BANK CALLBACK ERROR]',repr(e),flush=True)

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

async def promo_command_handler(m):
    a=app(); uid=m.from_user.id; text=(m.text or '').strip()
    if not await is_subscribed(a,uid):
        await m.answer(sub_text(),reply_markup=sub_keyboard(),parse_mode='HTML'); return
    parts=text.split(maxsplit=1)
    if len(parts)==2:
        ok,msg=a.db.use_promo(uid,parts[1].strip()); a.state.pop(uid,None)
        await m.answer((f'🎉 <b>Промокод активирован!</b>\n`{SEP}`\n\n{msg}\n\n{a.bal(uid)}') if ok else '❌ '+msg,parse_mode='HTML'); return
    a.state[uid]={'promo':True}
    await m.answer(f'🎟 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n`{SEP}`\n\nВведите промокод сообщением ниже.',parse_mode='HTML',reply_markup=a.one_back('home'))

async def promo_state_input(m,a):
    uid=m.from_user.id; s=a.state.get(uid,{})
    if not s.get('promo'): return False
    code=(m.text or '').strip(); ok,msg=a.db.use_promo(uid,code); a.state.pop(uid,None)
    await m.answer((f'🎉 <b>Промокод активирован!</b>\n`{SEP}`\n\n{msg}\n\n{a.bal(uid)}') if ok else '❌ '+msg,parse_mode='HTML'); return True

async def bank_message_handler(m):
    a=app(); uid=m.from_user.id; txt=(m.text or '').strip(); low=txt.lower()
    if not txt or txt.startswith('/'): raise SkipHandler()
    if (s:=a.state.get(uid)) and s.get('bank')=='amount': return await bank_state_input(m,a)
    if (s:=a.state.get(uid)) and s.get('promo'): return await promo_state_input(m,a)
    if low in ('промо','промокод'):
        a.state[uid]={'promo':True}; await m.answer(f'🎟 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n`{SEP}`\n\nВведите промокод сообщением ниже.',parse_mode='HTML',reply_markup=a.one_back('home')); return
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
                rows=[list(row) for row in kb.inline_keyboard]
                if not any(any(getattr(btn,'callback_data',None)=='bank' for btn in row) for row in rows):
                    from aiogram.types import InlineKeyboardButton
                    rows.insert(0,[InlineKeyboardButton(text='🏦 Банк',callback_data='bank')])
                kb.inline_keyboard=rows
            except Exception as e: print('[BANK MENU ERROR]',repr(e),flush=True)
            return kb
        main_wrap._hold_bank_brand=True; a.main_k=main_wrap
    old_set=getattr(a.bot,'set_my_commands',None)
    if callable(old_set) and not getattr(old_set,'_hold_bank_commands',False):
        async def set_commands(commands,*args,**kwargs):
            commands=list(commands or [])
            if not any(getattr(x,'command',None)=='bank' for x in commands): commands.append(BotCommand(command='bank',description='🏦 Банк'))
            return await old_set(commands,*args,**kwargs)
        set_commands._hold_bank_commands=True; a.bot.set_my_commands=set_commands

def patch_currency_display(a):
    """Replace legacy currency labels only in rendered admin/top text.
    Database columns and internal currency keys remain goldcoin/gold.
    """
    # Keep the actual settings authoritative for every future balance render.
    a.db.set_setting('primary_name','hCoin')
    a.db.set_setting('premium_name','HPOINT')
    a.db.set_setting('rate','45000')
    a.db.c.commit()

    old_top=getattr(a,'top_text',None)
    if callable(old_top) and not getattr(old_top,'_hold_currency_brand',False):
        def top_wrap():
            text=old_top()
            return text.replace('GOLDCOIN', a.currency_primary()).replace('Goldcoin', a.currency_primary()).replace('gold', a.currency_premium())
        top_wrap._hold_currency_brand=True
        a.top_text=top_wrap

    # admin_page builds several legacy examples directly into its text.
    # Patch only its rendered text, without changing internal DB currency keys.
    old_show=getattr(a,'show',None)
    if callable(old_show) and not getattr(old_show,'_hold_currency_display',False):
        async def branded_show(target,text,markup=None):
            if isinstance(text,str):
                text=text.replace('Goldcoin', a.currency_primary()).replace('GOLDCOIN', a.currency_primary())
                # Replace standalone display label, while preserving words like goldcoin internally.
                text=re.sub(r'(?<![A-Za-z])gold(?![A-Za-z])', a.currency_premium(), text, flags=re.IGNORECASE)
            return await old_show(target,text,markup)
        branded_show._hold_currency_display=True
        a.show=branded_show

def inject(a,dispatcher=None,original_include=None):
    init_db(a)
    if not hasattr(a,'r'): return
    patch_branding(a)
    patch_currency_display(a)
    a.r.callback_query.register(bank_callback,F.data.startswith('bank:') | (F.data=='bank'))
    a.r.message.register(bank_command_handler,Command('bank'))
    a.r.message.register(promo_command_handler,Command('promo'))
    a.r.message.register(bank_message_handler,F.text)
    a.r.callback_query.register(subscription_callback_guard,F.data.startswith('subscription:'))
    a.r.message.register(subscription_message_guard,F.text)
    try:
        for observer in (a.r.callback_query,a.r.message):
            if getattr(observer,'handlers',None):
                handlers=observer.handlers
                if observer is a.r.callback_query: priority=[h for h in handlers if h.callback in (bank_callback,subscription_callback_guard)]
                else: priority=[h for h in handlers if h.callback in (bank_command_handler,promo_command_handler,bank_message_handler,subscription_message_guard)]
                rest=[h for h in handlers if h not in priority]; observer.handlers=priority+rest
    except Exception as e: print('[BANK ORDER WARNING]',repr(e),flush=True)
    print('[EXT] Holdgame bank + promo keywords + currency branding installed with priority.',flush=True)
