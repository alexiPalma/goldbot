import html
from decimal import Decimal, InvalidOperation
from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router(name='gold_bank')
SEP='·····················'

def init_db(a):
    if not hasattr(a,'db'):
        a.db=a.DB
    a.db.c.execute('''CREATE TABLE IF NOT EXISTS bank_deposits(uid INTEGER PRIMARY KEY, amount TEXT NOT NULL, rate TEXT NOT NULL, created_at REAL NOT NULL, claimed INTEGER DEFAULT 0)''')
    a.db.set_setting('bank_rate', a.db.setting('bank_rate') or '5')
    a.db.set_setting('project_name', a.db.setting('project_name') or 'GOLDGAME')
    a.db.set_setting('primary_name', a.db.setting('primary_name') or 'Goldcoin')
    a.db.set_setting('premium_name', a.db.setting('premium_name') or 'gold')
    a.db.c.commit()

def pcur(a): return a.db.setting('primary_name') or 'Goldcoin'
def project(a): return a.db.setting('project_name') or 'GOLDGAME'
def rate(a):
    try:return Decimal(a.db.setting('bank_rate') or '5')
    except:return Decimal('5')

def bank_text(a,uid):
    row=a.db.c.execute('SELECT amount,rate,created_at,claimed FROM bank_deposits WHERE uid=?',(uid,)).fetchone()
    if not row:
        return f'🏦 <b>БАНК</b>\n`{SEP}`\n\n📈 Процент: <b>{rate(a):g}% за 24 часа</b>\n\nРазмести {pcur(a)} во вклад и получи проценты через 24 часа.'
    amount=Decimal(row['amount']); r=Decimal(row['rate']); profit=amount*r/100
    if row['claimed']:
        return f'🏦 <b>БАНК</b>\n`{SEP}`\n\nАктивного вклада нет.\n\n📈 Текущая ставка: <b>{rate(a):g}% за 24 часа</b>'
    import time
    left=max(0,86400-(time.time()-float(row['created_at'])))
    if left<=0:
        status=f'✅ <b>Вклад готов к получению!</b>\n\n💰 Вклад: <b>{a.fmt(amount)} {pcur(a)}</b>\n📈 Процент: <b>{r:g}%</b>\n🎉 Доход: <b>+{a.fmt(profit)} {pcur(a)}</b>\n💵 К получению: <b>{a.fmt(amount+profit)} {pcur(a)}</b>'
    else:
        h=int(left//3600); m=int((left%3600)//60)
        status=f'⏳ До получения: <b>{h} ч. {m} мин.</b>\n\n💰 Вклад: <b>{a.fmt(amount)} {pcur(a)}</b>\n📈 Процент: <b>{r:g}%</b>\n🎉 Доход: <b>+{a.fmt(profit)} {pcur(a)}</b>\n💵 Получишь: <b>{a.fmt(amount+profit)} {pcur(a)}</b>'
    return f'🏦 <b>БАНК</b>\n`{SEP}`\n\n{status}'

def bank_markup(a,uid):
    b=InlineKeyboardBuilder()
    row=a.db.c.execute('SELECT amount,created_at,claimed FROM bank_deposits WHERE uid=?',(uid,)).fetchone()
    if row and not row['claimed']:
        import time
        if time.time()-float(row['created_at'])>=86400:b.button(text='💰 Забрать вклад',callback_data='bank:claim')
    else:b.button(text='🏦 Вклад',callback_data='bank:deposit')
    b.button(text='◀️ Назад',callback_data='home'); b.adjust(1,1); return b.as_markup()

@router.callback_query(F.data=='bank')
async def bank_open(c):
    a=__import__('sys').modules.get('__main__'); uid=c.from_user.id
    a.db.user(uid,c.from_user.username,c.from_user.first_name)
    await c.answer(); await c.message.edit_text(bank_text(a,uid),reply_markup=bank_markup(a,uid),parse_mode='HTML')

@router.callback_query(F.data=='bank:deposit')
async def bank_deposit(c):
    a=__import__('sys').modules.get('__main__'); uid=c.from_user.id
    a.state[uid]={'bank':'amount'}; await c.answer(); await c.message.edit_text(f'🏦 <b>ВКЛАД</b>\n`{SEP}`\n\n💰 Сколько {pcur(a)} вы хотите положить?\n\nВведите сумму:',parse_mode='HTML',reply_markup=a.one_back('bank'))

@router.callback_query(F.data=='bank:cancel')
async def bank_cancel(c):
    a=__import__('sys').modules.get('__main__'); a.state.pop(c.from_user.id,None); await c.answer(); await c.message.edit_text(bank_text(a,c.from_user.id),reply_markup=bank_markup(a,c.from_user.id),parse_mode='HTML')

@router.callback_query(F.data=='bank:confirm')
async def bank_confirm(c):
    a=__import__('sys').modules.get('__main__'); uid=c.from_user.id; s=a.state.get(uid,{})
    try:amount=Decimal(s.get('amount','0'))
    except:amount=Decimal('0')
    if amount<=0 or a.db.balance(uid)[0]<amount:return await c.answer('Недостаточно средств.',show_alert=True)
    a.db.c.execute('UPDATE users SET balance=balance-? WHERE id=?',(str(amount),uid));a.db.c.execute('INSERT OR REPLACE INTO bank_deposits(uid,amount,rate,created_at,claimed) VALUES(?,?,?,?,0)',(uid,str(amount),str(rate(a)),__import__('time').time()));a.db.c.commit();a.state.pop(uid,None);await c.answer('Вклад открыт!');await c.message.edit_text(bank_text(a,uid),reply_markup=bank_markup(a,uid),parse_mode='HTML')

@router.callback_query(F.data=='bank:claim')
async def bank_claim(c):
    a=__import__('sys').modules.get('__main__');uid=c.from_user.id;row=a.db.c.execute('SELECT amount,rate,created_at,claimed FROM bank_deposits WHERE uid=?',(uid,)).fetchone()
    if not row or row['claimed'] or __import__('time').time()-float(row['created_at'])<86400:return await c.answer('Вклад ещё недоступен.',show_alert=True)
    amount=Decimal(row['amount']);profit=amount*Decimal(row['rate'])/100;total=amount+profit;a.db.c.execute('UPDATE users SET balance=balance+? WHERE id=?',(str(total),uid));a.db.c.execute('UPDATE bank_deposits SET claimed=1 WHERE uid=?',(uid,));a.db.c.commit();await c.answer('Вклад получен!');await c.message.edit_text(bank_text(a,uid),reply_markup=bank_markup(a,uid),parse_mode='HTML')

async def amount_input(m,a):
    uid=m.from_user.id
    if a.state.get(uid,{}).get('bank')!='amount':return False
    text=m.text.strip().replace("'",'').replace(',','.')
    try:amount=Decimal(text)
    except:return await m.answer('❌ Введите положительное целое число.'),True
    if amount<=0 or amount!=amount.to_integral_value():return await m.answer('❌ Введите положительное целое число.'),True
    if a.db.balance(uid)[0]<amount:return await m.answer(f'❌ Недостаточно {pcur(a)}.\n\nБаланс: <b>{a.fmt(a.db.balance(uid)[0])} {pcur(a)}</b>',parse_mode='HTML'),True
    r=rate(a);profit=amount*r/100;total=amount+profit;a.state[uid]={'bank':'confirm','amount':str(amount)};b=InlineKeyboardBuilder();b.button(text='✅ Подтвердить',callback_data='bank:confirm');b.button(text='❌ Отмена',callback_data='bank:cancel');b.adjust(1,1)
    await m.answer(f'🏦 <b>ПОДТВЕРЖДЕНИЕ ВКЛАДА</b>\n`{SEP}`\n\n💰 Вклад: <b>{a.fmt(amount)} {pcur(a)}</b>\n📈 Процент: <b>{r:g}% за 24 часа</b>\n🎉 Доход: <b>+{a.fmt(profit)} {pcur(a)}</b>\n💵 Вернётся: <b>{a.fmt(total)} {pcur(a)}</b>\n\nВсё верно?',reply_markup=b.as_markup(),parse_mode='HTML');return True

def install(a):
    # Integrate bank amount input into the existing text-state handler.
    old=getattr(a,'_gold_bank_state_wrapped',False)
    if old:return
    if hasattr(a,'state_input'):
        orig=a.state_input
        async def wrapped(m):
            handled=await amount_input(m,a)
            if handled:return
            return await orig(m)
        a.state_input=wrapped
    a._gold_bank_state_wrapped=True

def inject(a,dispatcher,original_include):
    init_db(a);install(a)
    if not getattr(dispatcher,'_gold_bank_router',False):
        # original_include is a bound Dispatcher.include_router method.
        original_include(router)
        dispatcher._gold_bank_router=True
