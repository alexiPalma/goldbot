import time, html
from decimal import Decimal, InvalidOperation
from aiogram import Router, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

SEP='·····················'

def app():
    import sys
    return sys.modules.get('__main__') or sys.modules.get('bot')

def init_db(a):
    a.db.c.execute('''CREATE TABLE IF NOT EXISTS bank_deposits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        principal TEXT NOT NULL,
        rate TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        claimed_at INTEGER
    )''')
    if not a.db.setting('bank_rate'): a.db.set_setting('bank_rate','5')
    if not a.db.setting('project_name'): a.db.set_setting('project_name','GOLDGAME')
    return a.db.c

def pname(a): return a.db.setting('project_name') or 'GOLDGAME'
def pcur(a): return a.db.setting('primary_name') or 'Goldcoin'
def scur(a): return a.db.setting('premium_name') or 'gold'
def bank_active(a,uid):
    init_db(a); return a.db.c.execute('SELECT * FROM bank_deposits WHERE user_id=? AND claimed_at IS NULL ORDER BY id DESC LIMIT 1',(uid,)).fetchone()

def bank_markup(a,uid):
    b=InlineKeyboardBuilder(); dep=bank_active(a,uid)
    if dep:
        left=max(0,86400-(int(time.time())-int(dep['created_at'])))
        b.button(text='💰 Забрать вклад + проценты' if left<=0 else '⏳ Проверить вклад',callback_data='bank:claim' if left<=0 else 'bank:refresh')
    else: b.button(text='🏦 Вклад',callback_data='bank:deposit')
    b.button(text='◀️ Назад',callback_data='home'); b.adjust(1,1); return b.as_markup()

def bank_text(a,uid):
    init_db(a); rate=Decimal(a.db.setting('bank_rate') or '5'); dep=bank_active(a,uid)
    out=f'🏦 <b>БАНК</b>\n`{SEP}`\n\nПроцент по вкладу: <b>{rate:g}% в сутки</b>\n\n'
    if dep:
        principal=Decimal(dep['principal']); profit=principal*Decimal(dep['rate'])/100; left=max(0,86400-(int(time.time())-int(dep['created_at'])))
        out+=f'💰 Вклад: <b>{a.fmt(principal)} {pcur(a)}</b>\n📈 Доход: <b>+{a.fmt(profit)} {pcur(a)}</b>\n' + (f'⏳ До получения: <b>{a.cd(left)}</b>' if left else '✅ Вклад готов к получению.')
    else: out+=f'На данный момент у тебя нет активного вклада.\n\n{a.bal(uid)}'
    return out

def bank_admin_text(a):
    rate=Decimal(a.db.setting('bank_rate') or '5'); return f'🏦 <b>БАНК — НАСТРОЙКИ</b>\n`{SEP}`\n\nТекущий процент: <b>{rate:g}% в сутки</b>\n\nОтправь новый процент одним числом, например:\n<code>7.5</code>'

def brand_admin_text(a):
    return f'🏷 <b>НАЗВАНИЯ</b>\n`{SEP}`\n\nНазвание проекта: <b>{html.escape(pname(a))}</b>\nОсновная валюта: <b>{html.escape(pcur(a))}</b>\nДополнительная валюта: <b>{html.escape(scur(a))}</b>\n\nВыбери, что изменить:'

def brand_k():
    b=InlineKeyboardBuilder(); b.button(text='🏷 Название проекта',callback_data='brand:project'); b.button(text='💰 Основная валюта',callback_data='brand:primary'); b.button(text='🪙 Доп. валюта',callback_data='brand:premium'); b.button(text='◀️ Назад',callback_data='admin'); b.adjust(1,1,1,1); return b.as_markup()

def add_button(markup,text,data):
    rows=[list(r) for r in (markup.inline_keyboard if markup else [])]; rows.append([InlineKeyboardButton(text=text,callback_data=data)]); return InlineKeyboardMarkup(inline_keyboard=rows)
def is_main_markup(m):
    if not m:return False
    v=[b.callback_data for r in m.inline_keyboard for b in r if b.callback_data]; return 'play' in v and 'profile' in v and 'ref' in v
def is_admin_markup(m):
    if not m:return False
    v=[b.callback_data for r in m.inline_keyboard for b in r if b.callback_data]; return 'a:currency' in v and 'a:money' in v

def install(a):
    init_db(a)
    from aiogram import Bot
    if getattr(Bot,'_gold_ext_patched',False): return
    old_send,old_edit=Bot.send_message,Bot.edit_message_text
    async def send(self,*args,**kwargs):
        text=kwargs.get('text',args[1] if len(args)>1 else None); markup=kwargs.get('reply_markup')
        if is_main_markup(markup): markup=add_button(markup,'🏦 Банк','bank')
        if is_admin_markup(markup): markup=add_button(add_button(markup,'🏦 Банк','a:bank'),'🏷 Названия','a:brand')
        if text:
            text=text.replace('GOLDGAME',pname(a)).replace('Goldcoin',pcur(a)).replace('gold',scur(a))
            if 'text' in kwargs: kwargs['text']=text
            elif len(args)>1: args=list(args);args[1]=text;args=tuple(args)
        kwargs['reply_markup']=markup; return await old_send(self,*args,**kwargs)
    async def edit(self,*args,**kwargs):
        text=kwargs.get('text',args[2] if len(args)>2 else None); markup=kwargs.get('reply_markup')
        if is_main_markup(markup): markup=add_button(markup,'🏦 Банк','bank')
        if is_admin_markup(markup): markup=add_button(add_button(markup,'🏦 Банк','a:bank'),'🏷 Названия','a:brand')
        if text: kwargs['text']=text.replace('GOLDGAME',pname(a)).replace('Goldcoin',pcur(a)).replace('gold',scur(a))
        kwargs['reply_markup']=markup; return await old_edit(self,*args,**kwargs)
    Bot.send_message=send; Bot.edit_message_text=edit; Bot._gold_ext_patched=True

router=Router(name='bank_brand')

@router.callback_query(F.data=='bank')
async def bank_open(c):
    a=app(); uid=c.from_user.id; a.db.user(uid,c.from_user.username,c.from_user.first_name); await c.answer(); await c.message.edit_text(bank_text(a,uid),reply_markup=bank_markup(a,uid),parse_mode='HTML')
@router.callback_query(F.data=='bank:deposit')
async def bank_deposit(c):
    a=app();uid=c.from_user.id;await c.answer()
    if bank_active(a,uid): return await c.message.edit_text(bank_text(a,uid),reply_markup=bank_markup(a,uid),parse_mode='HTML')
    a.state[uid]={'bank':'amount'}; await c.message.edit_text(f'🏦 <b>ВКЛАД</b>\n`{SEP}`\n\nСколько {pcur(a)} ты хочешь положить во вклад?\n\n{a.bal(uid)}\n\nВведи сумму сообщением ниже.',reply_markup=a.one_back('bank'),parse_mode='HTML')
@router.callback_query(F.data=='bank:cancel')
async def bank_cancel(c):
    a=app();a.state.pop(c.from_user.id,None);await c.answer();await c.message.edit_text(bank_text(a,c.from_user.id),reply_markup=bank_markup(a,c.from_user.id),parse_mode='HTML')
@router.callback_query(F.data=='bank:confirm')
async def bank_confirm(c):
    a=app();uid=c.from_user.id;s=a.state.get(uid,{})
    if s.get('bank')!='confirm': return await c.answer('Вклад уже обработан.',show_alert=True)
    amount=Decimal(str(s['amount']));rate=Decimal(a.db.setting('bank_rate') or '5')
    if a.db.balance(uid)[0]<amount:return await c.answer('❌ Недостаточно средств.',show_alert=True)
    if bank_active(a,uid):return await c.answer('❌ У тебя уже есть активный вклад.',show_alert=True)
    if not a.db.add(uid,'Goldcoin',-amount,'bank_deposit'):return await c.answer('❌ Не удалось оформить вклад.',show_alert=True)
    init_db(a);a.db.c.execute('INSERT INTO bank_deposits(user_id,principal,rate,created_at) VALUES(?,?,?,?)',(uid,str(amount),str(rate),int(time.time())));a.db.c.commit();a.state.pop(uid,None)
    await c.message.edit_text(f'✅ <b>ВКЛАД ОФОРМЛЕН</b>\n`{SEP}`\n\n💰 Сумма: <b>{a.fmt(amount)} {pcur(a)}</b>\n📈 Процент: <b>{rate:g}% в сутки</b>\n\n⏳ Получить вклад и проценты можно через 24 часа.',reply_markup=bank_markup(a,uid),parse_mode='HTML')
@router.callback_query(F.data=='bank:claim')
async def bank_claim(c):
    a=app();uid=c.from_user.id;dep=bank_active(a,uid)
    if not dep:return await c.answer('Активного вклада нет.',show_alert=True)
    if int(time.time())-int(dep['created_at'])<86400:return await c.answer('❌ 24 часа ещё не прошли.',show_alert=True)
    principal=Decimal(dep['principal']);profit=principal*Decimal(dep['rate'])/100;total=principal+profit
    if not a.db.add(uid,'Goldcoin',total,'bank_claim'):return await c.answer('❌ Не удалось зачислить вклад.',show_alert=True)
    a.db.c.execute('UPDATE bank_deposits SET claimed_at=? WHERE id=?',(int(time.time()),dep['id']));a.db.c.commit();await c.answer();await c.message.edit_text(f'🎉 <b>ВКЛАД ВОЗВРАЩЁН</b>\n`{SEP}`\n\n💰 Вклад: <b>{a.fmt(principal)} {pcur(a)}</b>\n📈 Проценты: <b>+{a.fmt(profit)} {pcur(a)}</b>\n\n💵 Получено: <b>{a.fmt(total)} {pcur(a)}</b>\n\n{a.bal(uid)}',reply_markup=bank_markup(a,uid),parse_mode='HTML')
@router.callback_query(F.data=='bank:refresh')
async def bank_refresh(c):
    a=app();await c.answer();await c.message.edit_text(bank_text(a,c.from_user.id),reply_markup=bank_markup(a,c.from_user.id),parse_mode='HTML')
@router.callback_query(F.data=='a:bank')
async def bank_admin(c):
    a=app()
    if not a.is_admin(c.from_user.id):return await c.answer('⛔ Нет доступа.',show_alert=True)
    a.state[c.from_user.id]={'admin':'bank'};await c.answer();await c.message.edit_text(bank_admin_text(a),reply_markup=a.one_back('admin'),parse_mode='HTML')
@router.callback_query(F.data=='a:brand')
async def brand_admin(c):
    a=app()
    if not a.is_admin(c.from_user.id):return await c.answer('⛔ Нет доступа.',show_alert=True)
    await c.answer();await c.message.edit_text(brand_admin_text(a),reply_markup=brand_k(),parse_mode='HTML')
@router.callback_query(F.data.startswith('brand:'))
async def brand_prompt(c):
    a=app();uid=c.from_user.id
    if not a.is_admin(uid):return await c.answer('⛔ Нет доступа.',show_alert=True)
    kind=c.data.split(':',1)[1];labels={'project':'название проекта','primary':'название основной валюты','premium':'название дополнительной валюты'};a.state[uid]={'admin':'brand_'+kind};await c.answer();await c.message.edit_text(f'🏷 <b>ИЗМЕНЕНИЕ НАЗВАНИЯ</b>\n`{SEP}`\n\nВведи новое {labels.get(kind,"название")}:',reply_markup=a.one_back('a:brand'),parse_mode='HTML')

def _bank_brand_filter(m):
    a=app()
    if a is None or not getattr(m,'text',None) or not getattr(m,'from_user',None):return False
    st=getattr(a,'state',{}).get(m.from_user.id,{})
    return bool(st.get('bank') in ('amount','confirm') or st.get('admin') in ('bank','brand_project','brand_primary','brand_premium'))
@router.message(_bank_brand_filter)
async def bank_brand_input(m):
    a=app();uid=m.from_user.id;s=a.state.get(uid,{});text=(m.text or '').strip()
    if s.get('bank')=='amount':
        try:amount=Decimal(text.replace("'",'').replace(',','.'))
        except InvalidOperation:return await m.answer('❌ Введи корректное число.')
        if amount<=0 or amount!=amount.to_integral_value():return await m.answer('❌ Сумма должна быть положительным целым числом.')
        if a.db.balance(uid)[0]<amount:return await m.answer(f'❌ Недостаточно {pcur(a)}.\n\nБаланс: <b>{a.fmt(a.db.balance(uid)[0])} {pcur(a)}</b>',parse_mode='HTML')
        rate=Decimal(a.db.setting('bank_rate') or '5');profit=amount*rate/100;total=amount+profit;a.state[uid]={'bank':'confirm','amount':str(amount)};b=InlineKeyboardBuilder();b.button(text='✅ Подтвердить',callback_data='bank:confirm');b.button(text='❌ Отмена',callback_data='bank:cancel');b.adjust(1,1)
        return await m.answer(f'🏦 <b>ПОДТВЕРЖДЕНИЕ ВКЛАДА</b>\n`{SEP}`\n\n💰 Вклад: <b>{a.fmt(amount)} {pcur(a)}</b>\n📈 Процент: <b>{rate:g}% за 24 часа</b>\n🎉 Доход: <b>+{a.fmt(profit)} {pcur(a)}</b>\n💵 Вернётся: <b>{a.fmt(total)} {pcur(a)}</b>\n\nВсё верно?',reply_markup=b.as_markup(),parse_mode='HTML')
    if s.get('admin')=='bank':
        if not a.is_admin(uid):return
        try:rate=Decimal(text.replace(',','.'))
        except InvalidOperation:return await m.answer('❌ Процент должен быть числом.')
        if rate<0 or rate>1000:return await m.answer('❌ Процент должен быть от 0 до 1000.')
        a.db.set_setting('bank_rate',rate);a.state.pop(uid,None);return await m.answer(f'✅ Процент банка установлен: <b>{rate:g}% в сутки</b>',parse_mode='HTML')
    if s.get('admin') in ('brand_project','brand_primary','brand_premium'):
        if not a.is_admin(uid):return
        key={'brand_project':'project_name','brand_primary':'primary_name','brand_premium':'premium_name'}[s['admin']]
        if not text or len(text)>40:return await m.answer('❌ Название должно быть от 1 до 40 символов.')
        a.db.set_setting(key,text);a.state.pop(uid,None);return await m.answer(f'✅ Изменено: <b>{html.escape(text)}</b>',parse_mode='HTML')

def inject(a,dispatcher,original_include):
    init_db(a);install(a)
    if not getattr(dispatcher,'_gold_bank_router',False):
        original_include(dispatcher,router);dispatcher._gold_bank_router=True
