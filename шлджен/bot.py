import asyncio, html, logging, os, random, time
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, MenuButtonCommands, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import DB
from games import Games

load_dotenv()
TOKEN=os.getenv('BOT_TOKEN','').strip()
if not TOKEN: raise SystemExit('BOT_TOKEN is empty. Fill .env')
MASTERS={int(x) for x in os.getenv('MASTER_ADMIN_IDS','').split(',') if x.strip().isdigit()}
bot=Bot(TOKEN); dp=Dispatcher(); r=Router(); dp.include_router(r)
db=DB(os.getenv('DATABASE_PATH','goldcoin.db')); games=Games(db)
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
SEP='·····················'
state={}

# ---------- formatting ----------
def fmt(x):
    try:x=Decimal(str(x))
    except: x=Decimal(0)
    return f"{x:,.0f}".replace(',','\'')
def cd(sec):
    sec=max(0,int(sec)); h=sec//3600; m=(sec%3600)//60; s=sec%60
    if h:return f'{h}ч. {m:02d}м.'
    if m:return f'{m}м. {s:02d}с.'
    return f'{s}с.'
def currency_primary():return db.setting('primary_name') or 'Goldcoin'
def currency_premium():return db.setting('premium_name') or 'gold'
def is_admin(uid):return uid in MASTERS or uid in db.admins()
def is_master(uid):return uid in MASTERS
def display_user(u):
    if not u:return 'Игрок'
    label=(' @'+u['username']) if u['username'] else (u['first_name'] or 'Игрок')
    return f"<a href='tg://user?id={u['id']}'>{html.escape(label.strip())}</a>"
def uname(uid):return display_user(db.user(uid))
def bal(uid):
    p,g=db.balance(uid)
    return f"💰 <b>{fmt(p)} {html.escape(currency_primary())}</b>\n🪙 <b>{fmt(g)} {html.escape(currency_premium())}</b>"

# ---------- keyboards ----------
def main_k(uid):
    b=InlineKeyboardBuilder()
    items=[('🎮 Игры','play'),('🎁 Бонус','bonus'),('📅 Ежедневный','daily'),('🎒 Лотерея','lottery'),('📦 Кейсы','cases'),('💸 Перевод','transfer'),('💱 Обменник','exchange'),('💰 Заработать','earn'),('👤 Профиль','profile'),('👥 Рефералы','ref'),('🏆 Мировой топ','top'),('💳 Донат','donate'),('🎟 Промокод','promo'),('❓ Помощь','help'),('📕 Правила','rules')]
    for t,d in items:b.button(text=t,callback_data=d)
    if is_admin(uid):b.button(text='👑 Админ-панель',callback_data='admin')
    b.adjust(2,2,2,2,2,2,2,1); return b.as_markup()
def one_back(dest='home'):
    b=InlineKeyboardBuilder(); b.button(text='◀️ Назад',callback_data=dest); return b.as_markup()
def play_k():
    b=InlineKeyboardBuilder()
    for t,d in [('🏀 Баскетбол','game:basket'),('⚽ Футбол','game:football'),('🎯 Дартс','game:darts'),('🎲 Кубик','game:dice'),('🎳 Боулинг','game:bowling'),('🎰 Спин','game:spin'),('💣 Мины','game:mines'),('🃏 21 очко','game:21'),('🗼 Башня','game:tower'),('🪙 Монета','game:coin'),('🎲 Кости','game:dice2')]:b.button(text=t,callback_data=d)
    b.button(text='◀️ Назад',callback_data='home'); b.adjust(2,2,2,2,2,2,1); return b.as_markup()
def bet_k(game):
    b=InlineKeyboardBuilder()
    for x in (10,100,1000,10000,100000):b.button(text=fmt(x),callback_data=f'bet:{game}:{x}')
    b.button(text='◀️ Назад',callback_data='play'); b.adjust(2,2,1,1); return b.as_markup()
def result_k(dest='play'):
    b=InlineKeyboardBuilder(); b.button(text='🔄 Играть ещё',callback_data=dest); b.button(text='🏠 Главное меню',callback_data='home'); b.adjust(1,1); return b.as_markup()
def mines_k(g):
    b=InlineKeyboardBuilder()
    for i in range(25):b.button(text='💎' if i in g['opened'] else '⬜',callback_data=f'mine:{i}')
    b.button(text=f'💰 Забрать · {fmt(g["bet"]*g["mult"])}',callback_data='mine:cash'); b.button(text='◀️ Игры',callback_data='play'); b.adjust(5,5,5,5,5,1,1); return b.as_markup()
def tower_k():
    b=InlineKeyboardBuilder()
    for i in range(3):b.button(text='🚪',callback_data=f'tower:{i}')
    b.button(text='💰 Забрать',callback_data='tower:cash'); b.button(text='◀️ Игры',callback_data='play'); b.adjust(3,2); return b.as_markup()
def bj_k():
    b=InlineKeyboardBuilder(); b.button(text='🃏 Взять',callback_data='bj:hit'); b.button(text='✋ Стоп',callback_data='bj:stop'); b.button(text='◀️ Игры',callback_data='play'); b.adjust(2,1); return b.as_markup()
def coin_k(amt):
    b=InlineKeyboardBuilder(); b.button(text='🦅 Орёл',callback_data=f'coin:Орёл:{amt}'); b.button(text='🪙 Решка',callback_data=f'coin:Решка:{amt}'); b.button(text='◀️ Назад',callback_data='play'); b.adjust(2,1); return b.as_markup()
def dice_guess_k(amt):
    b=InlineKeyboardBuilder()
    for i in range(1,7):b.button(text=str(i),callback_data=f'dicepick:{i}:{amt}')
    b.button(text='◀️ Назад',callback_data='play'); b.adjust(3,3,1); return b.as_markup()
def dice_condition_target_k(amt):
    b=InlineKeyboardBuilder()
    for i in range(1,7):b.button(text=f'Меньше {i}',callback_data=f'dicecond:lt:{i}:{amt}'); b.button(text=f'Равно {i}',callback_data=f'dicecond:eq:{i}:{amt}'); b.button(text=f'Больше {i}',callback_data=f'dicecond:gt:{i}:{amt}')
    b.button(text='◀️ Назад',callback_data='play'); b.adjust(3,3,3,3,1); return b.as_markup()
def case9_k(kind,opened=None):
    opened=opened or set(); b=InlineKeyboardBuilder()
    for i in range(1,10):
        b.button(text=('🔓' if i in opened else '📦'),callback_data=f'casepick:{kind}:{i}')
    b.button(text='❌ Отмена',callback_data='cases'); b.adjust(3,3,3,1); return b.as_markup()

def freecase_k():
    b=InlineKeyboardBuilder();
    for i in range(1,10):b.button(text='🎁',callback_data=f'freepick:{i}')
    b.button(text='◀️ Назад',callback_data='cases'); b.adjust(3,3,3,1); return b.as_markup()
def case_k():
    b=InlineKeyboardBuilder(); b.button(text='🆓 Free',callback_data='case:free'); b.button(text=f'💡 Light · {fmt(db.setting("light_price"))}',callback_data='case:light'); b.button(text=f'⚡ Express · {fmt(db.setting("express_price"))}',callback_data='case:express'); b.button(text='◀️ Назад',callback_data='home'); b.adjust(2,1,1); return b.as_markup()
def help_k():
    b=InlineKeyboardBuilder(); b.button(text='ℹ️ Основные',callback_data='help:main'); b.button(text='🎮 Игры',callback_data='play'); b.button(text='📕 Правила',callback_data='rules'); b.button(text='◀️ Назад',callback_data='home'); b.adjust(2,1,1); return b.as_markup()
def admin_k():
    b=InlineKeyboardBuilder()
    items=[('💰 Валюта и курс','a:currency'),('🎁 Бонусы','a:bonus'),('📦 Кейсы','a:cases'),('🎟 Промокоды','a:promo'),('📢 Заработать','a:earn'),('💳 Донат','a:donate'),('📕 Правила','a:rules'),('👥 Админы','a:admins'),('💸 Выдать / списать','a:money'),('📣 Рассылка','a:broadcast'),('📊 Статистика','a:stats')]
    for t,d in items:b.button(text=t,callback_data=d)
    b.button(text='◀️ Назад',callback_data='home'); b.adjust(2,2,2,2,2,2); return b.as_markup()

def home_text(uid):
    return f"✨ <b>GOLDGAME</b>\n`{SEP}`\n\n{bal(uid)}\n\nВыбери нужный раздел в меню."
def play_text():return f"🎮 <b>ИГРЫ</b>\n`{SEP}`\n\nВыбери игру и ставку:"
def lottery_text():return f"🎒 <b>ЛОТТЕРЕЯ</b>\n`{SEP}`\n\n10 сумок. В одной — 10'000, в другой — 3'000, в третьей — 100 Goldcoin. Остальные пустые.\n\nПопытка доступна раз в день."
def profile_text(uid):
    u=db.user(uid); p,g=db.balance(uid); rank=db.user_rank(uid); played=u['games']; dt=time.strftime('%d-%m-%Y %H:%M',time.localtime(u['created_at']))
    return f"<b>Профиль:</b> {uname(uid)}\n`{SEP}`\n├ <b>Статус:</b> Игрок\n├ <b>Сыграно игр:</b> {played}\n├ <b>Место в топе:</b> {rank:,}\n├ <b>Оборот:</b> {fmt(u['turnover'])} {currency_primary()}\n├ <b>Выиграно:</b> {u['wins']}\n├ <b>Проиграно:</b> {u['losses']}\n\n<blockquote>Дата регистрации: {dt}</blockquote>\n`{SEP}`\n{bal(uid)}"
def top_text():
    rows=db.leaderboard(10); lines=['<b>🏆 МИРОВОЙ ТОП ПО GOLDCOIN</b>', '`'+SEP+'`']
    for i,u in enumerate(rows,1): lines.append(f"{i}. {display_user(u)} | <code>{fmt(u['goldcoin'])}</code>")
    return '\n'.join(lines)
def ref_text(uid):
    u=db.user(uid); count=db.c.execute('SELECT COUNT(*) n FROM users WHERE referrer=? AND referred_paid=1',(uid,)).fetchone()['n']; earned=db.c.execute("SELECT COALESCE(SUM(CAST(amount AS REAL)),0) s FROM transactions WHERE user_id=? AND kind='referral'",(uid,)).fetchone()['s']; me=bot_username_cache[0] if bot_username_cache else 'your_bot'
    link=f'https://t.me/{me}?start=ref_{uid}'
    return f"<b>ПРИГЛАСИТЬ ДРУЗЕЙ</b>\n`{SEP}`\n\nПриглашайте друзей по своей ссылке и получайте бонусы:\n\n• <b>{fmt(db.setting('ref_reward'))} {currency_primary()}</b> за каждого друга\n• <b>{db.setting('ref_loss_pct')}%</b> от проигрыша друзей\n\n<b>Твоя ссылка:</b>\n⤷ <code>{html.escape(link)}</code>\n\n<b>Уже заработано:</b> ⤷ <code>{fmt(earned)} {currency_primary()}</code>\n<b>Приглашено друзей:</b> ⤷ <code>{count} чел.</code>\n\n<blockquote>Бонус начисляется сразу после регистрации нового пользователя по твоей ссылке.</blockquote>"
def help_main_text():
    return f"📖 <b>МЕНЮ ПОМОЩИ</b>\n`{SEP}`\n\nℹ️ Здесь собраны основные команды и их назначение.\n\n<b>Основные команды:</b>\n/play — игры\n/bonus — обычный бонус\n/daily — ежедневный бонус\n/lottery — лотерея\n/cases — кейсы\n/transfer — перевод Goldcoin\n/exchange — обмен gold → Goldcoin\n/earn — заработать\n/profile — профиль\n/ref — рефералы\n/top — мировой топ\n/donate — донат\n/promo — промокод\n/help — помощь\n/rules — правила"


# ---------- safe edit ----------
async def show(target, text, markup=None):
    try:
        if isinstance(target, CallbackQuery): target=target.message
        return await target.edit_text(text,reply_markup=markup,parse_mode='HTML')
    except Exception:
        if isinstance(target, Message): return await target.answer(text,reply_markup=markup,parse_mode='HTML')
        return await target.message.answer(text,reply_markup=markup,parse_mode='HTML')

# ---------- commands ----------
@r.message(Command('start'))
async def start(m:Message):
    u_before=db.c.execute('SELECT * FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    u=db.user(m.from_user.id,m.from_user.username,m.from_user.first_name)
    # Referral is credited exactly once to a genuinely new account.
    if not u_before and m.text and ' ' in m.text:
        payload=m.text.split(maxsplit=1)[1].strip()
        if payload.startswith('ref_') and payload[4:].isdigit():
            ref=int(payload[4:])
            if ref!=m.from_user.id and db.c.execute('SELECT 1 FROM users WHERE id=?',(ref,)).fetchone():
                db.c.execute('UPDATE users SET referrer=?, referred_paid=1 WHERE id=?',(ref,m.from_user.id)); db.c.commit()
                reward=Decimal(db.setting('ref_reward') or '15000'); db.add(ref,'Goldcoin',reward,'referral',m.from_user.id)
                try: await bot.send_message(ref,f"🎉 <b>НОВЫЙ РЕФЕРАЛ!</b>\n`{SEP}`\n\n👤 По твоей реферальной ссылке зарегистрирован новый игрок: {uname(m.from_user.id)}\n\n💰 Тебе начислено: <b>+{fmt(reward)} {currency_primary()}</b>\n\nПриглашено друзей: <b>{db.c.execute('SELECT COUNT(*) n FROM users WHERE referrer=? AND referred_paid=1',(ref,)).fetchone()['n']}</b>",parse_mode='HTML')
                except Exception: logging.exception('ref notify')
    await m.answer(home_text(m.from_user.id),reply_markup=main_k(m.from_user.id),parse_mode='HTML')

@r.message(Command('play'))
async def play(m): await m.answer(play_text(),reply_markup=play_k(),parse_mode='HTML')

@r.message(Command('bonus'))
async def bonus(m):
    uid=m.from_user.id
    if not db.cd_ready(uid,'bonus'):return await m.answer(f"⏳ <b>Попытка использована!</b> {uname(uid)}, возвращайся через: <b>{cd(db.cd_left(uid,'bonus'))}</b>.\n`{SEP}`\n\n{bal(uid)}",parse_mode='HTML')
    a=random.randint(int(db.setting('bonus_min')),int(db.setting('bonus_max'))); db.add(uid,'Goldcoin',a,'bonus'); db.set_cd(uid,'bonus',int(db.setting('bonus_cd')))
    await m.answer(f"🎁 {uname(uid)}, тебе был выдан бонус в размере: <b>{fmt(a)} {currency_primary()}!</b>\n`{SEP}`\n\n{bal(uid)}",parse_mode='HTML')

@r.message(Command('daily'))
async def daily(m):
    uid=m.from_user.id
    if not db.cd_ready(uid,'daily'):return await m.answer(f"📅 <b>Ежедневный бонус</b>\n`{SEP}`\n\nСледующий бонус через: <b>{cd(db.cd_left(uid,'daily'))}</b>.",parse_mode='HTML')
    a=random.randint(int(db.setting('daily_min')),int(db.setting('daily_max'))); db.add(uid,'Goldcoin',a,'daily'); db.set_cd(uid,'daily',86400)
    await m.answer(f"🎁 {uname(uid)}, ежедневный бонус: <b>+{fmt(a)} {currency_primary()}</b>\n`{SEP}`\n\n{bal(uid)}",parse_mode='HTML')

@r.message(Command('lottery'))
async def lottery(m): await open_lottery(m)
async def open_lottery(target):
    uid=target.from_user.id
    p=games.lottery(uid)
    if p is None:return await show(target,f"{lottery_text()}\n\n⏳ Попытка использована. Возвращайся через <b>{cd(db.cd_left(uid,'lottery'))}</b>.",one_back('home'))
    state[uid]={'lottery':p}
    b=InlineKeyboardBuilder()
    for i in range(10):b.button(text=f'🎒 {i+1}',callback_data=f'lot:{i}')
    b.button(text='◀️ Назад',callback_data='home'); b.adjust(5,5,1)
    return await show(target,lottery_text()+'\n\nВыбери одну сумку:',b.as_markup())

@r.message(Command('cases'))
async def cases(m):await m.answer(f"📦 <b>КЕЙСЫ</b>\n`{SEP}`\n\nВыбери кейс:",reply_markup=case_k(),parse_mode='HTML')

@r.message(Command('profile'))
async def profile(m):await m.answer(profile_text(m.from_user.id),parse_mode='HTML',reply_markup=one_back('home'))

@r.message(Command('top'))
async def top(m):await m.answer(top_text(),parse_mode='HTML',reply_markup=one_back('home'))

@r.message(Command('ref'))
async def ref(m):await m.answer(ref_text(m.from_user.id),parse_mode='HTML',reply_markup=one_back('home'))

@r.message(Command('transfer'))
async def transfer(m):
    await transfer_open(m)

async def transfer_open(target):
    uid=target.from_user.id
    state[uid]={'transfer':'username'}
    b=InlineKeyboardBuilder(); b.button(text='❌ Отмена',callback_data='transfer:cancel')
    return await show(target,f"💸 <b>ПЕРЕВОД</b>\n`{SEP}`\n\nУкажи <b>@username</b> получателя.\n\nНапример: <code>@username</code>",b.as_markup())

def transfer_currency_k():
    b=InlineKeyboardBuilder(); b.button(text='💰 Goldcoin',callback_data='transfer:currency:Goldcoin'); b.button(text='🪙 gold',callback_data='transfer:currency:gold'); b.button(text='❌ Отмена',callback_data='transfer:cancel'); b.adjust(2,1); return b.as_markup()

def transfer_confirm_k():
    b=InlineKeyboardBuilder(); b.button(text='✅ Подтвердить',callback_data='transfer:confirm'); b.button(text='❌ Отмена',callback_data='transfer:cancel'); b.adjust(1); return b.as_markup()

@r.message(Command('exchange'))
async def exchange_cmd(m): await exchange_open(m)
async def exchange_open(target):
    uid=target.from_user.id; g=db.balance(uid)[1]
    b=InlineKeyboardBuilder();b.button(text='💱 Обменять',callback_data='exchange:start');b.button(text='◀️ Назад',callback_data='home');b.adjust(1,1)
    return await show(target,f"<b>P2P ОБМЕННИК</b>\n`{SEP}`\n\nЗдесь ты можешь обменять <b>{currency_premium()}</b> на {currency_primary()}.\n\nКурс: <b>1 {currency_premium()} = {fmt(db.rate())} {currency_primary()}</b>\n\nТвой баланс: <b>{fmt(g)} {currency_premium()}</b>\n`{SEP}`\n\nЧто ты хочешь сделать?",b.as_markup())

@r.message(Command('earn'))
async def earn(m):await earn_open(m)
async def earn_open(target):
    uid=target.from_user.id; ch=db.earn_channels(); b=InlineKeyboardBuilder()
    for x in ch:
        if x['username']:b.button(text='📢 '+x['title'],url='https://t.me/'+x['username'].lstrip('@'))
    b.button(text='✅ Проверить подписки',callback_data='earn:check');b.button(text='◀️ Назад',callback_data='home');b.adjust(1)
    total=sum(Decimal(x['reward'] or db.setting('earn_reward')) for x in ch)
    txt=f"{uname(uid)}, здесь ты можешь заработать {currency_primary()}!\n`{SEP}`\nЗаданий на подписку: <b>{len(ch)}</b>\nЗаданий на просмотр: <b>0</b>\nЗаданий на вступление: <b>0</b>\n`{SEP}`\n<b>Можно заработать: {fmt(total)} {currency_primary()}</b>"
    return await show(target,txt,b.as_markup())

@r.message(Command('donate'))
async def donate(m):await m.answer(db.text('donate'),parse_mode='HTML',reply_markup=one_back('home'))

@r.message(Command('promo'))
async def promo(m):
    parts=m.text.split(maxsplit=1)
    if len(parts)==2:
        ok,msg=db.use_promo(m.from_user.id,parts[1]); return await m.answer((f"🎉 <b>Промокод активирован!</b>\n`{SEP}`\n\n{msg}\n\n{bal(m.from_user.id)}") if ok else '❌ '+msg,parse_mode='HTML')
    state[m.from_user.id]={'promo':True}; await m.answer(f"🎟 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n`{SEP}`\n\nВведите промокод сообщением ниже.",parse_mode='HTML',reply_markup=one_back('home'))

@r.message(Command('cancel'))
async def cancel(m):state.pop(m.from_user.id,None);await m.answer('❌ Текущее действие отменено.')

@r.message(Command('help'))
async def help_cmd(m):await m.answer(f"📖 <b>МЕНЮ ПОМОЩИ</b>\n`{SEP}`\n\nℹ️ Здесь собраны команды и разделы, которые могут тебе понадобиться.",reply_markup=help_k(),parse_mode='HTML')

@r.message(Command('rules'))
async def rules(m):await m.answer(db.text('rules'),parse_mode='HTML',reply_markup=one_back('home'))

# ---------- callbacks ----------
@r.callback_query()
async def cb(c:CallbackQuery):
    uid=c.from_user.id; db.user(uid,c.from_user.username,c.from_user.first_name); d=c.data or ''
    try:
        await c.answer()
        if d=='home':await show(c,home_text(uid),main_k(uid))
        elif d=='play':await show(c,play_text(),play_k())
        elif d=='bonus':
            await bonus(c.message)
        elif d=='daily':await daily(c.message)
        elif d=='lottery':await open_lottery(c)
        elif d=='cases':await show(c,f"📦 <b>КЕЙСЫ</b>\n`{SEP}`\n\nВыбери кейс:",case_k())
        elif d=='profile':await show(c,profile_text(uid),one_back('home'))
        elif d=='top':await show(c,top_text(),one_back('home'))
        elif d=='ref':await show(c,ref_text(uid),one_back('home'))
        elif d=='donate':await show(c,db.text('donate'),one_back('home'))
        elif d=='earn':await earn_open(c)
        elif d=='help':await show(c,f"📖 <b>МЕНЮ ПОМОЩИ</b>\n`{SEP}`\n\nℹ️ Здесь собраны команды и разделы, которые могут тебе понадобиться.",help_k())
        elif d=='help:main':await show(c,help_main_text(),one_back('help'))
        elif d=='rules':await show(c,db.text('rules'),one_back('help'))
        elif d=='transfer':await transfer_open(c)
        elif d=='transfer:cancel':
            state.pop(uid,None); await show(c,home_text(uid),main_k(uid))
        elif d.startswith('transfer:currency:'):
            cur=d.split(':',2)[2]; s=state.get(uid,{})
            if s.get('transfer')!='currency': return await c.answer('Начни перевод заново.',show_alert=True)
            s.update({'transfer':'amount','currency':cur}); state[uid]=s
            await show(c,f"💸 <b>СУММА ПЕРЕВОДА</b>\n`{SEP}`\n\nВведи количество <b>{cur}</b>, которое хочешь перевести.\n\n{bal(uid)}",one_back('transfer'))
        elif d=='transfer:confirm':
            s=state.get(uid,{})
            if s.get('transfer')!='confirm': return await c.answer('Перевод уже завершён.',show_alert=True)
            dst=db.find(s.get('username','')); amount=Decimal(str(s.get('amount','0'))); cur=s.get('currency','')
            if not dst: state.pop(uid,None); return await c.answer('Пользователь не найден.',show_alert=True)
            ok,msg=db.transfer(uid,dst['id'],cur,amount)
            if not ok:return await c.answer('❌ '+msg,show_alert=True)
            state.pop(uid,None)
            await show(c,f"✅ <b>ПЕРЕВОД ВЫПОЛНЕН</b>\n`{SEP}`\n\nПолучатель: {uname(dst['id'])}\nСумма: <b>{fmt(amount)} {html.escape(cur)}</b>\n\n{bal(uid)}",result_k('transfer'))
            try: await bot.send_message(dst['id'],f"💸 <b>ВАМ ПОСТУПИЛ ПЕРЕВОД</b>\n`{SEP}`\n\nОт: {uname(uid)}\nСумма: <b>{fmt(amount)} {html.escape(cur)}</b>\n\n{bal(dst['id'])}",parse_mode='HTML')
            except Exception: pass
        elif d=='exchange':await exchange_open(c)
        elif d=='exchange:start':
            state[uid]={'exchange':True}; await show(c,f"💱 <b>ОБМЕН GOLD</b>\n`{SEP}`\n\nСколько <b>{currency_premium()}</b> ты хочешь обменять?\n\nТвой баланс: <b>{fmt(db.balance(uid)[1])} {currency_premium()}</b>\n\nВведи количество сообщением ниже.",one_back('exchange'))
        elif d=='exchange:cancel':state.pop(uid,None);await exchange_open(c)
        elif d.startswith('game:'):
            game=d.split(':',1)[1]
            labels={'basket':'🏀 Баскетбол','football':'⚽ Футбол','darts':'🎯 Дартс','dice':'🎲 Кубик','bowling':'🎳 Боулинг','spin':'🎰 Спин','mines':'💣 Мины','21':'🃏 21 · игра идёт.','tower':'🗼 Башня','coin':'🪙 Монета','dice2':'🎲 Кости'}
            if game in ('mines','tower','21','basket','football','darts','dice','bowling','spin','coin','dice2'):await show(c,f"{labels[game]}\n`{SEP}`\n\nВыбери ставку:",bet_k(game))
        elif d.startswith('bet:'):
            _,game,amt=d.split(':'); amt=Decimal(amt)
            if db.balance(uid)[0] < amt:
                await show(c, f"❌ <b>Недостаточно {html.escape(currency_primary())}</b>\n`{SEP}`\n\nТвой баланс: <b>{fmt(db.balance(uid)[0])} {html.escape(currency_primary())}</b>\nТребуется: <b>{fmt(amt)} {html.escape(currency_primary())}</b>\n\nПополните баланс и попробуйте снова.", one_back('play'))
                return
            if game=='mines':
                if not games.mines_start(uid,amt):return await c.answer('❌ Игра уже идёт или ставка недоступна.',show_alert=True)
                g=games.mines[uid]; await show(c,f"💣 <b>МИНЫ</b>\n`{SEP}`\n\n💰 Ставка: <b>{fmt(amt)} {currency_primary()}</b>\n💣 Мин: <b>3</b>\n\nОткрывай клетки. Бомба заканчивает игру.",mines_k(g))
            elif game=='tower':
                if not games.tower_start(uid,amt):return await c.answer('❌ Игра уже идёт или ставка недоступна.',show_alert=True)
                await show(c,f"🗼 <b>БАШНЯ</b>\n`{SEP}`\n\n💰 Ставка: <b>{fmt(amt)} {currency_primary()}</b>\n📍 Высота: <b>1 / 6</b>\n\nВ каждом ряду одна бомба. Поднимайся выше или забирай выигрыш.",tower_k())
            elif game=='21':
                g=games.blackjack_start(uid,amt)
                if not g:return await c.answer('❌ Не удалось начать игру.',show_alert=True)
                await show(c,bj_text(g,hide=True),bj_k())
            elif game=='coin':await show(c,f"🪙 <b>МОНЕТА</b>\n`{SEP}`\n\nВыбери сторону:",coin_k(amt))
            elif game=='dice':await show(c,f"🎲 <b>КУБИК</b>\n`{SEP}`\n\nЗагадай число от <b>1 до 6</b>. Если Telegram-кубик выбросит именно его — победа.\n\nСтавка: <b>{fmt(amt)} {currency_primary()}</b>",dice_guess_k(amt))
            elif game=='dice2':await show(c,f"🎲 <b>КОСТИ</b>\n`{SEP}`\n\nВыбери условие и число:",dice_condition_target_k(amt))
            elif game in ('basket','football','darts','bowling'):await sports_game(c,game,amt)
            elif game=='spin':await spin_game(c,amt)
        elif d.startswith('mine:'):
            if d=='mine:cash':
                p=games.mines_cash(uid)
                if p is None:return await c.answer('Игра уже завершена.',show_alert=True)
                await show(c,f"💰 <b>МИНЫ — ВЫИГРЫШ</b>\n`{SEP}`\n\nТы забрал: <b>+{fmt(p)} {currency_primary()}</b>\n\n{bal(uid)}",result_k('game:mines'))
            else:
                res,g=games.mines_open(uid,int(d.split(':')[1]))
                if res is None:return await c.answer('Игра завершена.',show_alert=True)
                if res=='opened':return await c.answer('Эта клетка уже открыта.')
                if res=='bomb':await show(c,f"💥 <b>МИНА!</b>\n`{SEP}`\n\nТы открыл бомбу. Ставка <b>{fmt(g['bet'])} {currency_primary()}</b> потеряна.\n\n😔 Не повезло.",result_k('game:mines'))
                else:await show(c,f"💎 <b>Безопасно!</b>\n`{SEP}`\n\nМножитель: <b>{g['mult']:.2f}×</b>\nМожно забрать: <b>{fmt(g['bet']*g['mult'])} {currency_primary()}</b>",mines_k(g))
        elif d.startswith('tower:'):
            if d=='tower:cash':
                p=games.tower_cash(uid)
                if p is None:return await c.answer('Игра завершена.',show_alert=True)
                await show(c,f"💰 <b>БАШНЯ — ВЫИГРЫШ</b>\n`{SEP}`\n\nТы забрал: <b>+{fmt(p)} {currency_primary()}</b>",result_k('game:tower'))
            else:
                out=games.tower_pick(uid,int(d.split(':')[1]))
                if out is None:return await c.answer('Игра завершена.',show_alert=True)
                ok,p,f=out
                if not ok:await show(c,f"💥 <b>БАШНЯ — БОМБА!</b>\n`{SEP}`\n\nТы дошёл до <b>{f}-го этажа</b> и попался на бомбу.\n\n😔 Ставка потеряна. Не повезло.",result_k('game:tower'))
                elif f>=6:await show(c,f"🏆 <b>БАШНЯ ПРОЙДЕНА!</b>\n`{SEP}`\n\nТы прошёл все <b>6 высот</b>.\n\nВыигрыш: <b>+{fmt(p)} {currency_primary()}</b>",result_k('game:tower'))
                else:await show(c,f"🗼 <b>БАШНЯ</b>\n`{SEP}`\n\nПройдено: <b>{f} / 6</b>\nТекущий выигрыш: <b>{fmt(p)} {currency_primary()}</b>\n\nВыбери дверь следующего ряда:",tower_k())
        elif d.startswith('bj:'):
            if d=='bj:hit':
                g=games.blackjack_hit(uid)
                if not g:return await c.answer('Игра уже завершена.',show_alert=True)
                if games.hand(g['player'])>21:
                    out=games.blackjack_stop(uid);await show(c,bj_result(out),result_k('game:21'))
                else:await show(c,bj_text(g),bj_k())
            else:
                out=games.blackjack_stop(uid)
                if out:await show(c,bj_result(out),result_k('game:21'))
        elif d.startswith('coin:'):
            _,choice,amt=d.split(':'); bet=Decimal(amt)
            if db.balance(uid)[0] < bet or not db.add(uid,'Goldcoin',-bet,'coin_bet'):
                await show(c, f"❌ <b>Недостаточно {html.escape(currency_primary())}</b>\n`{SEP}`\n\nТвой баланс: <b>{fmt(db.balance(uid)[0])} {html.escape(currency_primary())}</b>\nТребуется: <b>{fmt(bet)} {html.escape(currency_primary())}</b>", one_back('play'))
                return
            # Telegram Bot API does not provide a native animated coin dice; only 🎲 🎯 🏀 ⚽ 🎳 🎰 are supported.
            # Therefore the toss is represented by emoji-only frames, with no text such as “Подбрасываем...”.
            anim=await c.message.answer('🪙')
            for frame in ('🪙','🦅','🪙','🦅','🪙'):
                await asyncio.sleep(.35)
                try: await anim.edit_text(frame)
                except Exception: pass
            v=random.choice(['Орёл','Решка']); win=v==choice; payout=bet*2 if win else Decimal(0)
            games.finish(uid,'coin',bet,v,payout,win)
            await anim.edit_text(f"🪙 <b>МОНЕТА</b>\n`{SEP}`\n\nВыпало: <b>{v}</b>\n\n"+(f"🎉 <b>Ты угадал!</b>\n💰 Выигрыш: <b>+{fmt(payout)} {currency_primary()}</b>" if win else f"❌ <b>Не угадал!</b>\n💸 Проигрыш: <b>−{fmt(bet)} {currency_primary()}</b>")+f"\n\n{bal(uid)}",parse_mode='HTML',reply_markup=result_k('game:coin'))
        elif d.startswith('dicepick:'):
            _,guess,amt=d.split(':'); await dice_animation(c,Decimal(amt),int(guess))
        elif d.startswith('dicecond:'):
            _,op,target,amt=d.split(':'); await dice_condition_animation(c,Decimal(amt),op,int(target))
        elif d.startswith('lot:'):
            p=state.get(uid,{}).get('lottery'); idx=int(d.split(':')[1])
            if not p:return await c.answer('Лотерея уже завершена.',show_alert=True)
            reward=int(p[idx]); state.pop(uid,None)
            if reward:db.add(uid,'Goldcoin',reward,'lottery')
            await show(c,f"🎒 <b>ЛОТТЕРЕЯ</b>\n`{SEP}`\n\n"+(f"🎉 В сумке был приз: <b>+{fmt(reward)} {currency_primary()}</b>" if reward else '😔 В этой сумке ничего нет. Повезёт завтра!')+f"\n\n{bal(uid)}",result_k('lottery'))
        elif d=='case:free':
            if not games.free_case_start(uid):return await c.answer(f"⏳ Free-кейс будет доступен через {cd(db.cd_left(uid,'freecase'))}.",show_alert=True)
            rewards=[Decimal(0),Decimal(0),Decimal(0),Decimal(100),Decimal(300),Decimal(500),Decimal(0),Decimal(0),Decimal(1000)]; random.shuffle(rewards)
            state[uid]={'free_attempts':2,'free_rewards':[str(x) for x in rewards],'free_opened':set()}; await show(c,f"🆓 <b>FREE CASE</b>\n`{SEP}`\n\nУ тебя <b>2 попытки</b>. Внутри 9 ячеек.\n\nВыбирай ячейку:",freecase_k())
        elif d.startswith('freepick:'):
            s=state.get(uid,{}); attempts=s.get('free_attempts',0); i=int(d.split(':')[1]); opened=set(s.get('free_opened',set()))
            if not attempts:return await c.answer('Открой Free-кейс заново.',show_alert=True)
            if i in opened:return await c.answer('Эта ячейка уже открыта.',show_alert=True)
            rewards=[Decimal(x) for x in s['free_rewards']]; reward=rewards[i-1]; opened.add(i); attempts-=1
            if reward:db.add(uid,'Goldcoin',reward,'freecase')
            if attempts:
                state[uid]={**s,'free_attempts':attempts,'free_opened':opened}; await show(c,f"🎁 <b>FREE CASE</b>\n`{SEP}`\n\n🔓 Ячейка <b>№{i}</b>: "+(f"🎉 <b>+{fmt(reward)} {currency_primary()}</b>" if reward else '😔 Пусто')+f"\n\nОсталась попытка: <b>{attempts}</b>",freecase_k())
            else:
                state.pop(uid,None); await show(c,f"🎁 <b>FREE CASE ЗАВЕРШЁН</b>\n`{SEP}`\n\n🔓 Ячейка <b>№{i}</b>: "+(f"🎉 <b>+{fmt(reward)} {currency_primary()}</b>" if reward else '😔 Пусто')+f"\n\nНовый кейс через: <b>{cd(db.cd_left(uid,'freecase'))}</b>\n\n{bal(uid)}",result_k('cases'))
        elif d in ('case:light','case:express'):
            typ=d.split(':')[1]; price=Decimal(db.setting(typ+'_price') or '0')
            if not games.cost(uid,price,'case_'+typ):return await c.answer('❌ Недостаточно Goldcoin.',show_alert=True)
            rewards=[Decimal(0),Decimal(0),price,price*2,price*3,Decimal(0),price*5,Decimal(0),price]; random.shuffle(rewards)
            state[uid]={'case':typ,'case_price':str(price),'case_rewards':[str(x) for x in rewards],'case_opened':set()}
            await show(c,f"📦 <b>{typ.title()} CASE</b>\n`{SEP}`\n\nЦена: <b>{fmt(price)} {currency_primary()}</b>\n\nВыбери одну из <b>9 ячеек</b>:",case9_k(typ))
        elif d.startswith('casepick:'):
            _,typ,idxs=d.split(':'); i=int(idxs); s=state.get(uid,{})
            if s.get('case')!=typ:return await c.answer('Кейс уже завершён.',show_alert=True)
            opened=set(s.get('case_opened',set()))
            if i in opened:return await c.answer('Эта ячейка уже открыта.',show_alert=True)
            rewards=[Decimal(x) for x in s['case_rewards']]; reward=rewards[i-1]; opened.add(i)
            if reward:db.add(uid,'Goldcoin',reward,'case_'+typ)
            state.pop(uid,None)
            await show(c,f"📦 <b>{typ.title()} CASE</b>\n`{SEP}`\n\n🔓 Открыта ячейка <b>№{i}</b>.\n\n"+(f"🎉 <b>Выигрыш: +{fmt(reward)} {currency_primary()}</b>" if reward else '😔 В этой ячейке ничего нет.')+f"\n\n{bal(uid)}",result_k('cases'))
        elif d=='earn:check':await earn_check(c)
        elif d=='exchange:confirm':
            s=state.get(uid,{})
            if s.get('exchange_confirm') is None:return await c.answer('Обмен уже завершён.',show_alert=True)
            a=Decimal(str(s['exchange_confirm'])); rate=db.rate(); g=db.balance(uid)[1]
            if a>g:return await c.answer('❌ Баланс gold изменился. Обмен отменён.',show_alert=True)
            if not db.add(uid,'gold',-a,'exchange'):return await c.answer('❌ Не удалось списать gold.',show_alert=True)
            if not db.add(uid,'Goldcoin',a*rate,'exchange'):
                db.add(uid,'gold',a,'exchange_rollback'); return await c.answer('❌ Не удалось зачислить Goldcoin.',show_alert=True)
            state.pop(uid,None); await show(c,f"✅ <b>ОБМЕН ВЫПОЛНЕН</b>\n`{SEP}`\n\nТы обменял <b>{fmt(a)} {currency_premium()}</b> на <b>{fmt(a*rate)} {currency_primary()}</b>.\n\n{bal(uid)}",result_k('exchange'))
        elif d=='admin:cancel':state.pop(uid,None);await show(c,'👑 <b>АДМИН-ПАНЕЛЬ</b>\n`'+SEP+'`\n\nВыбери действие:',admin_k())
        elif d=='admin':await admin_open(c)
        elif d.startswith('a:'):await admin_page(c,d[2:])
    except Exception:
        logging.exception('callback failed: %s',d)
        try:await c.answer('Ошибка обработки. Попробуйте ещё раз.',show_alert=True)
        except:pass

# ---------- game presentation ----------
def bj_text(g,hide=False):
    dealer=g['dealer']; shown='? • '+dealer[1] if hide else ' • '.join(dealer)+' | '+str(games.hand(dealer)); player=' • '.join(g['player'])+' | '+str(games.hand(g['player']))
    return f"<b>21 · игра идёт.</b>\n`{SEP}`\n\n<b>Ставка:</b> {fmt(g['bet'])} {currency_primary()}\n<b>Дилер:</b>\n> {shown}\n\n<b>Ты:</b>\n> {player}"
def bj_result(out):
    g,p,d,payout,win,tie=out
    res='🎉 Победа!' if win else ('🤝 Ничья! Ставка возвращена.' if tie else '😔 Проигрыш.')
    return f"<b>21 · результат</b>\n`{SEP}`\n\n<b>Ставка:</b> {fmt(g['bet'])} {currency_primary()}\n<b>Дилер:</b> {' • '.join(g['dealer'])} | {d}\n<b>Ты:</b> {' • '.join(g['player'])} | {p}\n\n{res}\n"+(f"+{fmt(payout)} {currency_primary()}" if payout else 'Ставка потеряна.')
async def dice_animation(c,bet,guess):
    if db.balance(c.from_user.id)[0] < bet:return await c.answer('❌ Недостаточно Goldcoin.',show_alert=True)
    if not db.add(c.from_user.id,'Goldcoin',-bet,'dice_bet'):return await c.answer('❌ Недостаточно Goldcoin.',show_alert=True)
    msg=await bot.send_dice(c.message.chat.id,emoji='🎲'); await asyncio.sleep(2)
    v=msg.dice.value; win=(v==guess); p=bet*Decimal(db.setting('dice_multiplier') or '6') if win else Decimal(0)
    games.finish(c.from_user.id,'dice',bet,f'guess:{guess};roll:{v}',p,win)
    await show(c,f"🎲 <b>КУБИК</b>\n`{SEP}`\n\nЗагадано: <b>{guess}</b>\nВыпало: <b>{v}</b>\n\n"+(f"🎉 <b>ПОПАЛ!</b>\n+{fmt(p)} {currency_primary()}" if win else '❌ <b>МИМО!</b>'),result_k('game:dice'))
async def dice_condition_animation(c,bet,op,target):
    if db.balance(c.from_user.id)[0] < bet:return await c.answer('❌ Недостаточно Goldcoin.',show_alert=True)
    if not db.add(c.from_user.id,'Goldcoin',-bet,'dice2_bet'):return await c.answer('❌ Недостаточно Goldcoin.',show_alert=True)
    msg=await bot.send_dice(c.message.chat.id,emoji='🎲'); await asyncio.sleep(2); v=msg.dice.value
    win={'lt':v<target,'eq':v==target,'gt':v>target}[op]; p=bet*Decimal('1.8') if win else Decimal(0)
    games.finish(c.from_user.id,'dice2',bet,f'{op}:{target};roll:{v}',p,win)
    words={'lt':'меньше','eq':'равно','gt':'больше'}
    await show(c,f"🎲 <b>КОСТИ</b>\n`{SEP}`\n\nУсловие: <b>{words[op]} {target}</b>\nВыпало: <b>{v}</b>\n\n"+(f"🎉 <b>Условие выполнено!</b>\n+{fmt(p)} {currency_primary()}" if win else '❌ <b>Условие не выполнено.</b>'),result_k('game:dice2'))
async def sports_game(c,game,bet):
    emoji={'basket':'🏀','football':'⚽','darts':'🎯','bowling':'🎳'}[game]
    labels={'basket':'Баскетбол','football':'Футбол','darts':'Дартс','bowling':'Боулинг'}
    # Charge before the animation so the result is deterministic in DB.
    # We cannot know Telegram's dice result before sending it, so reserve the stake and resolve from the real dice value.
    if not games.cost(c.from_user.id,bet,game+'_bet'):return await c.answer('❌ Недостаточно Goldcoin.',show_alert=True)
    msg=await bot.send_dice(c.message.chat.id,emoji=emoji); await asyncio.sleep(2); value=msg.dice.value
    win=value in ({'basket':{4,5},'football':{3,4,5},'darts':{6},'bowling':{6}}[game])
    payout=Decimal(bet)*Decimal(db.setting('sport_multiplier') or '2') if win else Decimal(0); games.finish(c.from_user.id,game,bet,'hit' if win else 'miss',payout,win)
    await show(c,f"{emoji} <b>{labels[game]}</b>\n`{SEP}`\n\n"+("🎯 <b>Попал!</b>\n💰 Выигрыш: <b>+"+fmt(payout)+f" {currency_primary()}</b>" if win else f"❌ <b>Мимо!</b>\n💸 Ставка: <b>−{fmt(bet)} {currency_primary()}</b>")+f"\n\n{bal(c.from_user.id)}",result_k(f'game:{game}'))
async def spin_game(c,bet):
    uid=c.from_user.id
    if not games.cost(uid,bet,'spin_bet'):return await c.answer('❌ Недостаточно Goldcoin.',show_alert=True)
    msg=await bot.send_dice(c.message.chat.id,emoji='🎰')
    await asyncio.sleep(2.2)
    value=msg.dice.value
    # Telegram slot value is 1..64; decode it into the same 3-reel result shown by the animation.
    v=int(value)
    # Telegram defines slot-machine value as three 2-bit reel values.
    # value 64 is the guaranteed 7-7-7 winning animation.
    if v==64:
        reels=['7️⃣','7️⃣','7️⃣']
    else:
        mapping=[1,2,3,0]
        symbols=['🍒','🍋','🔔','7️⃣']
        digits=[mapping[(v-1)&3], mapping[((v-1)>>2)&3], mapping[((v-1)>>4)&3]]
        reels=[symbols[d] for d in digits]
    win=len(set(reels))==1; payout=bet*Decimal(db.setting('spin_multiplier') or '5') if win else Decimal(0)
    games.finish(uid,'spin',bet,'|'.join(reels),payout,win)
    await show(c,f"🎰 <b>СПИН</b>\n`{SEP}`\n\n"+("🎉 <b>ТРИ ОДИНАКОВЫХ!</b>\n" if win else "😔 <b>Комбинация не собрана.</b>\n")+ (f"💰 Выигрыш: <b>+{fmt(payout)} {currency_primary()}</b>\n" if payout else f"💸 Ставка: <b>−{fmt(bet)} {currency_primary()}</b>\n")+f"\n{bal(uid)}",result_k('game:spin'))

async def earn_check(c):
    uid=c.from_user.id; ch=db.earn_channels(); ok=0
    for x in ch:
        if not x['chat_id']:
            ok+=1; continue
        try:
            member=await bot.get_chat_member(x['chat_id'],uid)
            if member.status in ('member','administrator','creator') or (member.status=='restricted' and getattr(member,'is_member',False)):ok+=1
        except: pass
    if ok<len(ch):return await c.answer(f'Подписано: {ok}/{len(ch)}. Подпишись на все задания.',show_alert=True)
    if not db.cd_ready(uid,'earn'):
        return await c.answer(f'Заработок снова будет доступен через {cd(db.cd_left(uid,"earn"))}.',show_alert=True)
    reward=sum(Decimal(x['reward'] or db.setting('earn_reward')) for x in ch)
    if reward>0:db.add(uid,'Goldcoin',reward,'earn');db.set_cd(uid,'earn',int(db.setting('earn_cd') or 86400))
    await show(c,f"🎉 <b>ЗАДАНИЯ ВЫПОЛНЕНЫ!</b>\n`{SEP}`\n\nТебе начислено: <b>+{fmt(reward)} {currency_primary()}</b>\n\n{bal(uid)}",result_k('earn'))

# ---------- admin ----------
def admin_open(c):
    if not is_admin(c.from_user.id):return c.answer('⛔ Нет доступа.',show_alert=True)
    return show(c,f"👑 <b>АДМИН-ПАНЕЛЬ</b>\n`{SEP}`\n\nВыбери действие:",admin_k())
def admin_prompt(text,action):
    b=InlineKeyboardBuilder();b.button(text='❌ Отмена',callback_data='admin:cancel'); return b.as_markup()
async def admin_page(c,sec):
    if not is_admin(c.from_user.id):return await c.answer('⛔ Нет доступа.',show_alert=True)
    uid=c.from_user.id
    if sec=='currency':
        txt=f"💰 <b>ВАЛЮТА И КУРС</b>\n`{SEP}`\n\nОсновная: <b>{currency_primary()}</b>\nДополнительная: <b>{currency_premium()}</b>\nКурс: <b>1 {currency_premium()} = {fmt(db.rate())} {currency_primary()}</b>\n\nОтправь одной строкой:\n<code>Goldcoin gold 1000000</code>"
        state[uid]={'admin':'currency'}
    elif sec=='bonus':
        txt=f"🎁 <b>БОНУСЫ</b>\n`{SEP}`\n\nОбычный: {db.setting('bonus_min')}–{db.setting('bonus_max')}\nКД: {db.setting('bonus_cd')} сек.\nЕжедневный: {db.setting('daily_min')}–{db.setting('daily_max')}\n\nОтправь:\n<code>100 1000 3600 1000 5000</code>\n(обычный min max cd, затем daily min max)"; state[uid]={'admin':'bonus'}
    elif sec=='cases':
        txt=f"📦 <b>КЕЙСЫ</b>\n`{SEP}`\n\nLight: {fmt(db.setting('light_price'))}\nExpress: {fmt(db.setting('express_price'))}\n\nОтправь: <code>10000 50000</code>"; state[uid]={'admin':'cases'}
    elif sec=='promo':
        rows=db.promos(); lst='\n'.join(f"• <code>{html.escape(x['code'])}</code> — {x['amount']} {x['currency']} — {x['uses']}/{x['max_uses'] or '∞'}" for x in rows) or 'Нет промокодов.'
        txt=f"🎟 <b>ПРОМОКОДЫ</b>\n`{SEP}`\n\n{lst}\n\nСоздать: <code>CODE goldcoin 50000 100</code>\nУдалить: <code>/delpromo CODE</code>"; state[uid]={'admin':'promo'}
    elif sec=='earn':
        ch=db.earn_channels(); lst='\n'.join(f"• @{x['username']} — {x['title']} — {x['reward']}" for x in ch) or 'Нет каналов.'
        txt=f"📢 <b>ЗАРАБОТАТЬ</b>\n`{SEP}`\n\n{lst}\n\nДобавить: <code>/earnadd @channel Название</code>\nУдалить: <code>/earndel @channel</code>"; state[uid]={'admin':'earn'}
    elif sec=='donate':txt="💳 <b>ДОНАТ</b>\n`{SEP}`\n\nОтправь новый текст доната следующим сообщением."; state[uid]={'admin':'donate'}
    elif sec=='rules':txt="📕 <b>ПРАВИЛА</b>\n`{SEP}`\n\nОтправь новый текст правил следующим сообщением."; state[uid]={'admin':'rules'}
    elif sec=='admins':
        lst='\n'.join('• '+uname(x) for x in db.admins()) or 'Нет дополнительных админов.'
        txt=f"👥 <b>АДМИНЫ</b>\n`{SEP}`\n\n{lst}\n\nТолько MASTER ID могут добавлять/удалять админов.\nДобавить: <code>/addadmin 123456</code>\nУдалить: <code>/deladmin 123456</code>"
    elif sec=='money':txt="💸 <b>ВЫДАТЬ / СПИСАТЬ</b>\n`{SEP}`\n\nВыдай: <code>/give @username goldcoin 1000</code>\nСписание: <code>/take @username goldcoin 1000</code>\n\nДоступны Goldcoin и gold."
    elif sec=='broadcast':txt="📣 <b>РАССЫЛКА</b>\n`{SEP}`\n\nОтправь:\n<code>/broadcast users Текст</code>\n<code>/broadcast groups Текст</code>\n<code>/broadcast all Текст</code>"
    elif sec=='stats':
        s=db.stats();txt=f"📊 <b>СТАТИСТИКА</b>\n`{SEP}`\n\nПользователей: <b>{s['users']}</b>\nГрупп: <b>{s['groups']}</b>\nТранзакций: <b>{s['tx']}</b>\nИгр: <b>{s['games']}</b>"
    else:txt='Неизвестный раздел.'
    await show(c,txt,admin_k())

@r.message(Command('admin'))
async def admin_cmd(m):
    if not is_admin(m.from_user.id):
        return await m.answer('⛔ <b>Доступ запрещён.</b>\n\nЭта команда доступна только администраторам.',parse_mode='HTML')
    await m.answer(f"👑 <b>АДМИН-ПАНЕЛЬ</b>\n`{SEP}`\n\nВыбери нужный раздел:",reply_markup=admin_k(),parse_mode='HTML')

@r.message(Command('give'))
async def give(m):
    if not is_admin(m.from_user.id):return
    p=m.text.split();
    if len(p)!=4:return await m.answer('/give @username goldcoin 1000')
    u=db.find(p[1]);
    if not u:return await m.answer('❌ Пользователь не найден.')
    try:v=Decimal(p[3])
    except:return await m.answer('❌ Сумма должна быть числом.')
    if v<=0 or not db.add(u['id'],p[2],v,'admin_give',m.from_user.id):return await m.answer('❌ Не удалось выдать валюту.')
    await m.answer(f"✅ Выдано: <b>+{fmt(v)} {p[2]}</b>\nПользователь: {uname(u['id'])}",parse_mode='HTML')
@r.message(Command('take'))
async def take(m):
    if not is_admin(m.from_user.id):return
    p=m.text.split();
    if len(p)!=4:return await m.answer('/take @username goldcoin 1000')
    u=db.find(p[1]);
    if not u:return await m.answer('❌ Пользователь не найден.')
    try:v=Decimal(p[3])
    except:return await m.answer('❌ Сумма должна быть числом.')
    if v<=0 or not db.add(u['id'],p[2],-v,'admin_take',m.from_user.id):return await m.answer('❌ Недостаточно средств или неверная валюта.')
    await m.answer(f"✅ Списано: <b>-{fmt(v)} {p[2]}</b>\nПользователь: {uname(u['id'])}",parse_mode='HTML')
@r.message(Command('addadmin'))
async def addadmin(m):
    if not is_master(m.from_user.id):return await m.answer('⛔ Только два MASTER ID могут менять админов.')
    p=m.text.split();
    if len(p)!=2:return await m.answer('/addadmin 123456789')
    u=db.find(p[1]); uid=int(p[1]) if p[1].isdigit() else (u['id'] if u else 0)
    if not uid:return await m.answer('❌ Пользователь не найден. Он должен открыть бота хотя бы один раз.')
    db.add_admin(uid);await m.answer(f'✅ {uname(uid)} добавлен в администраторы.',parse_mode='HTML')
@r.message(Command('deladmin'))
async def deladmin(m):
    if not is_master(m.from_user.id):return await m.answer('⛔ Только два MASTER ID могут менять админов.')
    p=m.text.split();
    if len(p)!=2:return await m.answer('/deladmin 123456789')
    uid=int(p[1]) if p[1].isdigit() else ((db.find(p[1]) or {'id':0})['id'])
    if not uid:return await m.answer('❌ Пользователь не найден.')
    db.del_admin(uid);await m.answer(f'✅ {uname(uid)} удалён из администраторов.',parse_mode='HTML')
@r.message(Command('createpromo'))
async def createpromo(m):
    if not is_admin(m.from_user.id):return
    p=m.text.split();
    if len(p)!=5:return await m.answer('/createpromo CODE goldcoin 50000 100')
    try:v=Decimal(p[3]); limit=int(p[4])
    except:return await m.answer('❌ Неверная сумма или лимит.')
    if v<=0 or limit<0:return await m.answer('❌ Сумма должна быть положительной, лимит — 0 или больше.')
    db.create_promo(p[1],p[2],v,limit);await m.answer(f'✅ Промокод <code>{html.escape(p[1].upper())}</code> создан.',parse_mode='HTML')
@r.message(Command('delpromo'))
async def delpromo(m):
    if is_admin(m.from_user.id) and len(m.text.split())==2:db.delete_promo(m.text.split()[1]);await m.answer('✅ Промокод отключён.')
@r.message(Command('earnadd'))
async def earnadd(m):
    if not is_admin(m.from_user.id):return
    p=m.text.split(maxsplit=2)
    if len(p)<3:return await m.answer('/earnadd @channel Название')
    user=p[1].lstrip('@');title=p[2]
    db.c.execute('INSERT INTO earn_channels(title,username,active,reward) VALUES(?,?,1,?)',(title,user,db.setting('earn_reward')));db.c.commit();await m.answer('✅ Канал добавлен.')
@r.message(Command('earndel'))
async def earndel(m):
    if is_admin(m.from_user.id) and len(m.text.split())==2:db.c.execute('UPDATE earn_channels SET active=0 WHERE username=?',(m.text.split()[1].lstrip('@'),));db.c.commit();await m.answer('✅ Канал удалён.')
@r.message(Command('setprimary'))
async def setprimary(m):
    if is_admin(m.from_user.id) and len(m.text.split())==2:db.set_setting('primary_name',m.text.split()[1]);await m.answer('✅ Основная валюта изменена.')
@r.message(Command('setpremium'))
async def setpremium(m):
    if is_admin(m.from_user.id) and len(m.text.split())==2:db.set_setting('premium_name',m.text.split()[1]);await m.answer('✅ Дополнительная валюта изменена.')
@r.message(Command('rate'))
async def rate(m):
    if not is_admin(m.from_user.id):return
    p=m.text.split();
    if len(p)==2:
        try:v=Decimal(p[1]); assert v>0
        except:return await m.answer('❌ Курс должен быть положительным числом.')
        db.set_setting('rate',v);return await m.answer('✅ Курс изменён.')
    await m.answer(f'1 {currency_premium()} = {fmt(db.rate())} {currency_primary()}')
@r.message(Command('bonussettings'))
async def bonussettings(m):
    if not is_admin(m.from_user.id):return
    p=m.text.split();
    if len(p)==6:
        for k,v in zip(('bonus_min','bonus_max','bonus_cd','daily_min','daily_max'),p[1:]):db.set_setting(k,v)
        await m.answer('✅ Настройки бонусов сохранены.')
@r.message(Command('caseprices'))
async def caseprices(m):
    if is_admin(m.from_user.id) and len(m.text.split())==3:db.set_setting('light_price',m.text.split()[1]);db.set_setting('express_price',m.text.split()[2]);await m.answer('✅ Цены кейсов изменены.')
@r.message(Command('donatetext'))
async def donatetext(m):
    if is_admin(m.from_user.id) and len(m.text.split(maxsplit=1))==2:db.set_text('donate',m.text.split(maxsplit=1)[1]);await m.answer('✅ Текст доната изменён.')
@r.message(Command('ruleset'))
async def ruleset(m):
    if is_admin(m.from_user.id) and len(m.text.split(maxsplit=1))==2:db.set_text('rules',m.text.split(maxsplit=1)[1]);await m.answer('✅ Правила обновлены.')
@r.message(Command('broadcast'))
async def broadcast(m):
    if not is_admin(m.from_user.id):return
    p=m.text.split(maxsplit=2)
    if len(p)<3:return await m.answer('/broadcast users Текст | groups Текст | all Текст')
    target,text=p[1].lower(),p[2]; ids=[]
    if target in ('users','all'):ids += [x['id'] for x in db.c.execute('SELECT id FROM users').fetchall()]
    if target in ('groups','all'):ids += db.group_ids()
    ok=bad=0
    for cid in dict.fromkeys(ids):
        try:await bot.send_message(cid,text,parse_mode='HTML');ok+=1
        except:bad+=1
        await asyncio.sleep(.03)
    await m.answer(f'📣 Рассылка завершена. Успешно: <b>{ok}</b>, ошибок: <b>{bad}</b>.',parse_mode='HTML')

# ---------- state input ----------
@r.message(F.text)
async def state_input(m:Message):
    uid=m.from_user.id; text=m.text.strip()
    if text.startswith('/'):return
    s=state.get(uid)
    if not s:return
    try:
        if s.get('promo'):
            state.pop(uid,None);ok,msg=db.use_promo(uid,text);return await m.answer((f"🎉 <b>Промокод активирован!</b>\n`{SEP}`\n\n{msg}\n\n{bal(uid)}") if ok else '❌ '+msg,parse_mode='HTML')
        if s.get('transfer')=='username':
            u=db.find(text)
            if not u:return await m.answer('❌ Пользователь не найден. Проверь @username и убедись, что пользователь уже запускал бота.')
            if u['id']==uid:return await m.answer('❌ Нельзя переводить самому себе.')
            state[uid]={'transfer':'currency','username':text}
            return await m.answer(f"💰 <b>ВЫБОР ВАЛЮТЫ</b>\n`{SEP}`\n\nПолучатель: {uname(u['id'])}\n\nКакую валюту переводим?",reply_markup=transfer_currency_k(),parse_mode='HTML')
        if s.get('transfer')=='amount':
            try:a=Decimal(text)
            except:return await m.answer('⚠️ Введи положительное целое число.')
            if a<=0 or a!=a.to_integral_value():return await m.answer('⚠️ Введи положительное целое число.')
            cur=s['currency']; p,g=db.balance(uid); available=p if cur.lower()=='goldcoin' else g
            if a>available:return await m.answer(f"❌ Недостаточно {cur}.\n\nДоступно: <b>{fmt(available)} {cur}</b>\nТребуется: <b>{fmt(a)} {cur}</b>",parse_mode='HTML')
            state[uid]={**s,'transfer':'confirm','amount':str(a)}
            dst=db.find(s['username'])
            return await m.answer(f"💸 <b>ПОДТВЕРЖДЕНИЕ ПЕРЕВОДА</b>\n`{SEP}`\n\nПолучатель: {uname(dst['id']) if dst else html.escape(s['username'])}\nВалюта: <b>{cur}</b>\nСумма: <b>{fmt(a)} {cur}</b>\n\nПосле подтверждения сумма будет списана с твоего баланса.\n\nУверен, что хочешь выполнить перевод?",reply_markup=transfer_confirm_k(),parse_mode='HTML')
        if s.get('exchange'):
            try:a=Decimal(text)
            except:return await m.answer('⚠️ Введите положительное целое число gold.')
            if a<=0:return await m.answer('⚠️ Количество должно быть больше нуля.')
            g=db.balance(uid)[1]
            if a>g:return await m.answer(f"❌ Недостаточно gold.\nДоступно: <b>{fmt(g)} {currency_premium()}</b>\nВы указали: <b>{fmt(a)}</b>",parse_mode='HTML')
            state[uid]={'exchange_confirm':a}
            amount=a*db.rate(); b=InlineKeyboardBuilder();b.button(text='✅ Подтвердить',callback_data='exchange:confirm');b.button(text='❌ Отмена',callback_data='exchange:cancel');b.adjust(1)
            return await m.answer(f"💱 <b>ПОДТВЕРЖДЕНИЕ ОБМЕНА</b>\n`{SEP}`\n\nТы хочешь обменять:\n🪙 <b>{fmt(a)} {currency_premium()}</b>\n\nна:\n💰 <b>{fmt(amount)} {currency_primary()}</b>\n\nКурс: 1 {currency_premium()} = {fmt(db.rate())} {currency_primary()}\n\nТы уверен?",reply_markup=b.as_markup(),parse_mode='HTML')
        if s.get('exchange_confirm') is not None:return
        if s.get('admin') and is_admin(uid):
            mode=s['admin']; parts=text.split()
            if mode=='currency' and len(parts)==3:db.set_setting('primary_name',parts[0]);db.set_setting('premium_name',parts[1]);db.set_setting('rate',parts[2])
            elif mode=='bonus' and len(parts)==5:
                for k,v in zip(('bonus_min','bonus_max','bonus_cd','daily_min','daily_max'),parts):db.set_setting(k,v)
            elif mode=='cases' and len(parts)==2:db.set_setting('light_price',parts[0]);db.set_setting('express_price',parts[1])
            elif mode=='promo' and len(parts)==4:
                # admin prompt format: CODE currency amount limit
                db.create_promo(parts[0],parts[1],Decimal(parts[2]),int(parts[3]))
            elif mode=='donate':db.set_text('donate',text)
            elif mode=='rules':db.set_text('rules',text)
            else:return await m.answer('❌ Формат не распознан. Открой раздел админ-панели и используй указанный формат.')
            state.pop(uid,None);return await m.answer('✅ Настройка сохранена.',reply_markup=admin_k())
    except Exception:
        logging.exception('state input')
        await m.answer('❌ Не удалось обработать ввод. Проверь формат.')

@r.my_chat_member()
async def group_event(e:ChatMemberUpdated):
    if e.chat.type in ('group','supergroup'):
        active=e.new_chat_member.status not in ('left','kicked')
        db.c.execute('INSERT INTO groups(id,title,active) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,active=excluded.active',(e.chat.id,e.chat.title or '',int(active)));db.c.commit()

bot_username_cache=[]
async def setup():
    global bot_username_cache
    cmds=[
      ('play','🎮 Игры'),('bonus','🎁 Бонус'),('daily','📅 Ежедневный'),('lottery','🎒 Лотерея'),('cases','📦 Кейсы'),('transfer','💸 Перевод'),('exchange','💱 Обменник'),('earn','💰 Заработать'),('profile','👤 Профиль'),('ref','👥 Рефералы'),('top','🏆 Мировой топ'),('donate','💳 Донат'),('promo','🎟 Промокод'),('help','📖 Помощь'),('rules','📕 Правила'),('start','🏠 Главное')]
    if MASTERS or db.admins():cmds.append(('admin','👑 Админ-панель'))
    bc=[BotCommand(command=a,description=b) for a,b in cmds]
    await bot.set_my_commands(bc,scope=BotCommandScopeAllPrivateChats()); await bot.set_my_commands(bc,scope=BotCommandScopeAllGroupChats()); await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    me=await bot.get_me(); bot_username_cache[:]=[me.username or '']
    logging.info('@%s started | masters=%s',me.username,sorted(MASTERS))

async def main():
    await setup(); await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types())
if __name__=='__main__':asyncio.run(main())
