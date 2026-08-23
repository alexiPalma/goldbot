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
# Correct dice conditions: only 2..5.
def dice_condition_target_k(amt):
 from aiogram.utils.keyboard import InlineKeyboardBuilder
 b=InlineKeyboardBuilder()
 for n in range(2,6):
  for op,word in (('lt','Меньше'),('eq','Равно'),('gt','Больше')):b.button(text=f'{word} {n}',callback_data=f'dicecond:{op}:{n}:{amt}')
 b.button(text='◀️ Назад',callback_data='play');b.adjust(3,3,3,3,1);return b.as_markup()
# Use the already complete v2 handler; the old start_bot keyword layer is removed.
import bot_extensions_v2 as vx
vx.install(db)
# Bank/promo handlers first, then state machine, then universal games/duels.
import bank_brand as bk
bk.inject(sys.modules['__main__'],dp,None)
async def bridge(m):
 s=state.get(m.from_user.id,{})
 if s.get('admin') or s.get('transfer') or s.get('exchange') or s.get('exchange_confirm') is not None:return await state_input(m)
 raise SkipHandler()
r.message.register(bridge,F.text & ~F.text.startswith('/'))
try:
 def mk(h):
  n=getattr(h.callback,'__name__','')
  return 0 if n in ('bank_message_handler','bank_command_handler','promo_command_handler') else (1 if h.callback is bridge else (2 if h.callback is vx._message else 3))
 r.message.handlers.sort(key=mk)
 def ck(h):
  n=getattr(h.callback,'__name__','');return 0 if n=='bank_callback' else (1 if h.callback is vx._callback else 2)
 r.callback_query.handlers.sort(key=ck)
except Exception:pass
# Button ownership: only the user who received a button can press it.
_OWN={}
_old_answer=Message.answer
if not getattr(Message,'_hold_owner_patch',False):
 async def _answer(self,*a,**kw):
  out=await _old_answer(self,*a,**kw)
  try:
   if getattr(out,'reply_markup',None) is not None:_OWN[(out.chat.id,out.message_id)]=self.from_user.id
  except:pass
  return out
 Message.answer=_answer;Message._hold_owner_patch=True
async def _owner(c):
 uid=_OWN.get((c.message.chat.id,c.message.message_id))
 if uid is not None and uid!=c.from_user.id:await c.answer();return
r.callback_query.register(_owner)
try:r.callback_query.handlers.insert(0,r.callback_query.handlers.pop())
except:pass
# Every sender is registered even when using a slash command.
async def register_user(m):db.user(m.from_user.id,m.from_user.username,m.from_user.first_name);raise SkipHandler()
r.message.register(register_user,F.text)
try:r.message.handlers.insert(0,r.message.handlers.pop())
except:pass
print('[HOTFIX] Holdgame final routing loaded: keywords, custom bets, duel, promo, transfer, exchange, bank, dice 2..5.',flush=True)
'''
def run():
 s=open(BOT,encoding='utf-8').read();mark="if __name__=='__main__':asyncio.run(main())"
 if mark not in s:raise RuntimeError('polling marker missing')
 exec(compile(s.replace(mark,PATCH+'\n'+mark,1),BOT,'exec'),globals(),globals())
while True:
 try:print('[BOT] Starting bot...',flush=True);run()
 except KeyboardInterrupt:print('[BOT] Stopped by user.',flush=True);break
 except SystemExit as e:print('[BOT] SystemExit:',e,flush=True)
 except Exception:print('[BOT] Unexpected crash:',flush=True);traceback.print_exc()
 time.sleep(5)
