import os,time,traceback,sys
BASE=os.path.dirname(os.path.abspath(__file__)); BOT=os.path.join(BASE,'bot.py')
PATCH=r'''
from aiogram.dispatcher.event.bases import SkipHandler
try:
 db.set_setting('primary_name','hCoin');db.set_setting('premium_name','HPOINT');db.set_setting('rate','45000');db.c.commit()
except:pass
try:
 old=home_text
 def home_text(uid):return old(uid).replace('GOLDGAME','Holdgame').replace('Goldgame','Holdgame')
 def top_text():
  rows=db.leaderboard(10);z=[f'<b>🏆 МИРОВОЙ ТОП ПО {html.escape(currency_primary())}</b>','`'+SEP+'`']
  z += [f'{i}. {display_user(u)} | <code>{fmt(u["goldcoin"])} {html.escape(currency_primary())}</code>' for i,u in enumerate(rows,1)];return '\n'.join(z)
except:pass

def dice_condition_target_k(amt):
 from aiogram.utils.keyboard import InlineKeyboardBuilder
 b=InlineKeyboardBuilder()
 for n in range(2,6):
  for op,word in (('lt','Меньше'),('eq','Равно'),('gt','Больше')):b.button(text=f'{word} {n}',callback_data=f'dicecond:{op}:{n}:{amt}')
 b.button(text='◀️ Назад',callback_data='play');b.adjust(3,3,3,3,1);return b.as_markup()

import bot_extensions_v2 as vx
vx.install(db)
import bank_brand as bk
bk.inject(sys.modules['__main__'],dp,None)

# ---------- 21 hotfix ----------
# If a player already has an unfinished 21 game, pressing the 21 button
# must reopen that game instead of returning the generic "Не удалось начать игру".
try:
 _old_blackjack_start=Games.blackjack_start
 def _blackjack_start_fixed(self,uid,bet):
  if uid in self.blackjack:
   return self.blackjack[uid]
  return _old_blackjack_start(self,uid,bet)
 Games.blackjack_start=_blackjack_start_fixed
except Exception:
 pass

# ---------- per-channel subscription reward ----------
# /earnadd @channel 5000 [Название]
async def earnadd_fixed(m):
    if not is_admin(m.from_user.id):
        raise SkipHandler()
    p=m.text.split()
    if len(p)<3:
        return await m.answer('/earnadd @channel 5000 [Название]')
    username=p[1].lstrip('@')
    try:
        reward=Decimal(p[2])
    except Exception:
        return await m.answer('❌ Сумма награды должна быть положительным числом.')
    if reward<=0:
        return await m.answer('❌ Сумма награды должна быть больше нуля.')
    title=' '.join(p[3:]).strip() or ('@'+username)
    db.c.execute('INSERT INTO earn_channels(title,username,active,reward) VALUES(?,?,1,?)',(title,username,str(reward)))
    db.c.commit()
    await m.answer(f'✅ Канал @{html.escape(username)} добавлен.\n💰 Награда за подписку: <b>{fmt(reward)} {html.escape(currency_primary())}</b>',parse_mode='HTML')

r.message.register(earnadd_fixed,Command('earnadd'))

async def quick_keywords(m):
    text=(m.text or '').strip(); low=' '.join(text.lower().split()); parts=low.split(); uid=m.from_user.id
    if not low or low.startswith('/'):
        raise SkipHandler()
    s=state.get(uid,{})
    # Never steal input belonging to an active flow. It goes to the proper state handler.
    if any(k in s for k in ('promo','transfer','exchange','exchange_confirm','admin','bank','custom_bet')):
        raise SkipHandler()
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
      'перевод':lambda: transfer_open(m),
      'донат':lambda: donate(m),
    }
    if low in simple:
        return await simple[low]()
    if low in ('банк','банка'):
        return await m.answer(bk.bank_text(sys.modules['__main__'],uid),reply_markup=bk.bank_menu(),parse_mode='HTML')
    if low in ('промо','промокод'):
        state[uid]={'promo':True};return await m.answer(f'🎟 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n`{SEP}`\n\nВведите промокод сообщением ниже.',parse_mode='HTML',reply_markup=one_back('home'))
    if low.startswith('промо ') or low.startswith('промокод '):
        code=text.split(maxsplit=1)[1].strip();ok,msg=db.use_promo(uid,code);return await m.answer((f'🎉 <b>Промокод активирован!</b>\n`{SEP}`\n\n{msg}\n\n{bal(uid)}') if ok else '❌ '+msg,parse_mode='HTML')
    if parts and parts[0] in ('перевод','перевести') and len(parts)==4:
        target,currency,amount_s=parts[1],parts[2],parts[3].replace("'",'').replace(',','.')
        try: amount=Decimal(amount_s)
        except: return await m.answer('⚠️ Сумма должна быть положительным целым числом.')
        if amount<=0 or amount!=amount.to_integral_value(): return await m.answer('⚠️ Сумма должна быть положительным целым числом.')
        dst=db.find(target)
        if not dst:return await m.answer('❌ Пользователь не найден. Убедись, что он уже запускал бота.')
        if dst['id']==uid:return await m.answer('❌ Нельзя переводить самому себе.')
        cur=db.normalize_currency(currency)
        if not cur:return await m.answer('❌ Неизвестная валюта. Используй hCoin или HPOINT.')
        ok,msg=db.transfer(uid,dst['id'],cur,amount)
        if not ok:return await m.answer('❌ '+msg)
        label=db.currency_label(cur);await m.answer(f'✅ <b>ПЕРЕВОД ВЫПОЛНЕН</b>\n`{SEP}`\n\nПолучатель: {uname(dst["id"])}\nСумма: <b>{fmt(amount)} {html.escape(label)}</b>\n\n{bal(uid)}',parse_mode='HTML')
        try:await bot.send_message(dst['id'],f'💸 <b>ВАМ ПОСТУПИЛ ПЕРЕВОД</b>\n`{SEP}`\n\nОт: {uname(uid)}\nСумма: <b>{fmt(amount)} {html.escape(label)}</b>\n\n{bal(dst["id"])}',parse_mode='HTML')
        except Exception:pass
        return
    raise SkipHandler()

async def bridge(m):
 s=state.get(m.from_user.id,{})
 if any(k in s for k in ('promo','admin','transfer','exchange','exchange_confirm','bank')):return await state_input(m)
 raise SkipHandler()
r.message.register(quick_keywords,F.text & ~F.text.startswith('/'))
r.message.register(bridge,F.text & ~F.text.startswith('/'))
try:
 def mk(h):
  n=getattr(h.callback,'__name__','')
  return 0 if n in ('bank_message_handler','bank_command_handler','promo_command_handler','earnadd_fixed') else (1 if h.callback is quick_keywords else (2 if h.callback is bridge else (3 if h.callback is vx._message else 4)))
 r.message.handlers.sort(key=mk)
 def ck(h):
  n=getattr(h.callback,'__name__','');return 0 if n=='bank_callback' else (1 if h.callback is vx._callback else 2)
 r.callback_query.handlers.sort(key=ck)
except Exception:pass
async def register_user(m):db.user(m.from_user.id,m.from_user.username,m.from_user.first_name);raise SkipHandler()
r.message.register(register_user,F.text)
try:r.message.handlers.insert(0,r.message.handlers.pop())
except:pass
print('[HOTFIX] Holdgame routing restored: quick keywords + games + duel + transfer + promo + bank + per-channel earn reward + 21.',flush=True)
'''
def run():
 s=open(BOT,encoding='utf-8').read();mark="if __name__=='__main__':asyncio.run(main())"
 if mark not in s:raise RuntimeError('polling marker missing')
 exec(compile(s.replace(mark,PATCH+'\n'+mark,1),BOT,'exec'),globals(),globals())
while True:
 try:print('[BOT] Starting bot...',flush=True);run()
 except KeyboardInterrupt:print('[BOT] Stopped by user.',flush=True);break
 except SystemExit as e:print('[BOT] SystemExit:',e,flush=True)
 except Exception as e:print('[BOT] Unexpected crash:',e,flush=True);traceback.print_exc()
 time.sleep(5)
