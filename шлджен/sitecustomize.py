"""Startup compatibility patch for the bot.

The project executes bot.py through start_bot.py with exec(compile(...)).
This module keeps legacy internal database names while fixing runtime message
routing for promo codes, transfers, exchange and game state input.
"""
import builtins
import os
import sys
from decimal import Decimal

_original_compile = builtins.compile

def _patched_compile(source, filename, mode, *args, **kwargs):
    if isinstance(source, str) and os.path.basename(str(filename)).lower() == 'bot.py':
        marker = "if __name__=='__main__':asyncio.run(main())"
        patch = r'''
# ---------- dynamic currency compatibility patch ----------
try:
    if db.setting('primary_name') in (None, '', 'Goldcoin', 'goldcoin'): db.set_setting('primary_name', 'hCoin')
    if db.setting('premium_name') in (None, '', 'gold', 'Gold'): db.set_setting('premium_name', 'HPOINT')
except Exception: pass
_old_home_text=home_text
def home_text(uid): return _old_home_text(uid).replace('GOLDGAME','Holdgame').replace('Goldgame','Holdgame').replace('goldgame','Holdgame')
_old_top_text=top_text
def top_text():
    rows=db.leaderboard(10); current=html.escape(currency_primary()); lines=[f'<b>🏆 МИРОВОЙ ТОП ПО {current}</b>','`'+SEP+'`']
    for i,u in enumerate(rows,1): lines.append(f"{i}. {display_user(u)} | <code>{fmt(u['goldcoin'])}</code>")
    return '\n'.join(lines)
_old_admin_page=admin_page
async def admin_page(c,sec):
    if sec=='currency':
        if not is_admin(c.from_user.id): return await c.answer('⛔ Нет доступа.',show_alert=True)
        uid=c.from_user.id; txt=f"💰 <b>ВАЛЮТА И КУРС</b>\n`{SEP}`\n\nОсновная: <b>{currency_primary()}</b>\nДополнительная: <b>{currency_premium()}</b>\nКурс: <b>1 {currency_premium()} = {fmt(db.rate())} {currency_primary()}</b>\n\nОтправь одной строкой:\n<code>{currency_primary()} {currency_premium()} 45000</code>"; state[uid]={'admin':'currency'}; return await show(c,txt,admin_k())
    if sec=='money':
        if not is_admin(c.from_user.id): return await c.answer('⛔ Нет доступа.',show_alert=True)
        txt=f"💸 <b>ВЫДАТЬ / СПИСАТЬ</b>\n`{SEP}`\n\nВыдать: <code>/give @username {currency_primary()} 1000</code>\nСписать: <code>/take @username {currency_primary()} 1000</code>\n\nДоступны {currency_primary()} и {currency_premium()}."; return await show(c,txt,admin_k())
    return await _old_admin_page(c,sec)
_old_lottery_text=lottery_text
def lottery_text(): return _old_lottery_text().replace('Goldcoin',currency_primary()).replace('goldcoin',currency_primary()).replace('Gold',currency_premium()).replace('gold',currency_premium())
'''
        if marker in source and 'dynamic currency compatibility patch' not in source: source=source.replace(marker,patch+'\n'+marker,1)
    return _original_compile(source,filename,mode,*args,**kwargs)

builtins.compile=_patched_compile

# ---------- message-routing compatibility patch ----------
# bot_extensions_v2 registers a broad non-command handler before bot.py's state_input.
try:
    from aiogram.dispatcher.event.telegram import TelegramEventObserver
    _observer_register=TelegramEventObserver.register
    if not getattr(TelegramEventObserver,'_hold_runtime_patch',False):
        def _hold_register(self,callback,*filters,**kwargs):
            if getattr(callback,'__name__','')!='_message': return _observer_register(self,callback,*filters,**kwargs)
            async def wrapped(message):
                a=sys.modules.get('__main__')
                if a is None: return await callback(message)
                text=(message.text or '').strip(); parts=text.lower().split(); uid=message.from_user.id
                if not text.startswith('/'):
                    if parts and parts[0] in ('промо','промокод'):
                        if len(parts)==1: return await a.promo(message)
                        if len(parts)==2:
                            ok,msg=a.db.use_promo(uid,parts[1]); return await message.answer((f"🎉 <b>Промокод активирован!</b>\n`{a.SEP}`\n\n{msg}\n\n{a.bal(uid)}") if ok else '❌ '+msg,parse_mode='HTML')
                        if len(parts)==5 and a.is_admin(uid):
                            try: v=Decimal(parts[3]); limit=int(parts[4])
                            except Exception: return await message.answer('❌ Неверная сумма или лимит.')
                            if v<=0 or limit<0: return await message.answer('❌ Сумма должна быть положительной, лимит — 0 или больше.')
                            try: a.db.create_promo(parts[1],parts[2],v,limit)
                            except Exception as e: return await message.answer('❌ '+str(e))
                            return await message.answer(f"✅ Промокод <code>{parts[1].upper()}</code> создан.",parse_mode='HTML')
                    if parts and parts[0] in ('перевод','transfer'):
                        if len(parts)==1: return await a.transfer_open(message)
                        if len(parts)==4:
                            dst=a.db.find(parts[1])
                            if not dst: return await message.answer('❌ Пользователь не найден. Он должен хотя бы один раз открыть бота.')
                            if dst['id']==uid: return await message.answer('❌ Нельзя переводить самому себе.')
                            try: amount=Decimal(parts[3].replace("'",''))
                            except Exception: return await message.answer('❌ Сумма должна быть положительным целым числом.')
                            if amount<=0 or amount!=amount.to_integral_value(): return await message.answer('❌ Сумма должна быть положительным целым числом.')
                            ok,msg=a.db.transfer(uid,dst['id'],parts[2],amount)
                            if not ok: return await message.answer('❌ '+msg)
                            label=a.db.currency_label(parts[2]); fs=f"{amount:,.0f}".replace(',','\'')
                            await message.answer(f"✅ <b>ПЕРЕВОД ВЫПОЛНЕН</b>\n`{a.SEP}`\n\nПолучатель: {a.uname(dst['id'])}\nСумма: <b>{fs} {label}</b>\n\n{a.bal(uid)}",parse_mode='HTML')
                            try: await a.bot.send_message(dst['id'],f"💸 <b>ВАМ ПОСТУПИЛ ПЕРЕВОД</b>\n`{a.SEP}`\n\nОт: {a.uname(uid)}\nСумма: <b>{fs} {label}</b>\n\n{a.bal(dst['id'])}",parse_mode='HTML')
                            except Exception: pass
                            return
                    if parts and parts[0] in ('обменник','обмен'): return await a.exchange_open(message)
                result=await callback(message)
                handler=getattr(a,'state_input',None)
                if handler: return await handler(message)
                return result
            wrapped.__name__='_message'; return _observer_register(self,wrapped,*filters,**kwargs)
        TelegramEventObserver.register=_hold_register
        TelegramEventObserver._hold_runtime_patch=True
except Exception:
    pass
