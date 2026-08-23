import sys, time, threading

_INSTALLED = False

def _ctx(): return sys.modules.get('__main__')

def _loop(games):
    while True:
        time.sleep(15)
        now=time.monotonic()
        for game, store in (('mines', games.mines), ('tower', games.towers)):
            for uid, g in list(store.items()):
                if now - games._hold_activity.get((game, uid), now) >= 300:
                    store.pop(uid, None); games._hold_activity.pop((game, uid), None)
                    try: games.db.add(uid, 'Goldcoin', g['bet'], game + '_timeout_refund')
                    except Exception: pass
                    try: games.db.record_game(uid, game, g['bet'], 'timeout', 0, False)
                    except Exception: pass

def _cancel(games, game, uid):
    store = games.mines if game == 'mines' else games.towers
    g = store.pop(uid, None); games._hold_activity.pop((game, uid), None)
    if not g: return None
    try: games.db.add(uid, 'Goldcoin', g['bet'], game + '_cancel_refund')
    except Exception: pass
    try: games.db.record_game(uid, game, g['bet'], 'cancel', 0, False)
    except Exception: pass
    return g['bet']

def _expired(games, game, uid):
    store = games.mines if game == 'mines' else games.towers
    g = store.get(uid)
    if not g: return False
    if time.monotonic() - games._hold_activity.get((game, uid), time.monotonic()) < 300: return False
    _cancel(games, game, uid); return True

def _install_router(a):
    if getattr(a, '_hold_mines_tower_router', False): return
    old_reg=a.r.callback_query.register
    def register(callback,*filters,**kwargs):
        if getattr(callback,'__name__','')!='cb': return old_reg(callback,*filters,**kwargs)
        async def wrapped(c):
            d=c.data or ''; uid=c.from_user.id; games=a.games
            if d in ('mine:cancel','tower:cancel'):
                game='mines' if d.startswith('mine:') else 'tower'; p=_cancel(games,game,uid); await c.answer()
                if p is None: return await c.answer('Игра уже завершена.',show_alert=True)
                return await a.show(c, f'❌ <b>ИГРА ОТМЕНЕНА</b>\n`{a.SEP}`\n\nСтавка <b>{a.fmt(p)} {a.currency_primary()}</b> возвращена.', a.result_k('game:'+game))
            if d.startswith('mine:') and _expired(games,'mines',uid): return await c.answer('Игра завершена по тайм-ауту. Ставка возвращена.',show_alert=True)
            if d.startswith('tower:') and _expired(games,'tower',uid): return await c.answer('Игра завершена по тайм-ауту. Ставка возвращена.',show_alert=True)
            if d.startswith('bet:mines'):
                old=a.mines_k
                if not getattr(old,'_hold_cancel',False):
                    def mk(g):
                        kb=old(g); from aiogram.utils.keyboard import InlineKeyboardBuilder
                        b=InlineKeyboardBuilder()
                        for row in kb.inline_keyboard: b.row(*row)
                        b.button(text='❌ Отмена игры',callback_data='mine:cancel'); return b.as_markup()
                    mk._hold_cancel=True; a.mines_k=mk
            if d.startswith('bet:tower'):
                old=a.tower_k
                if not getattr(old,'_hold_cancel',False):
                    def tk():
                        kb=old(); from aiogram.utils.keyboard import InlineKeyboardBuilder
                        b=InlineKeyboardBuilder()
                        for row in kb.inline_keyboard: b.row(*row)
                        b.button(text='❌ Отмена игры',callback_data='tower:cancel'); return b.as_markup()
                    tk._hold_cancel=True; a.tower_k=tk
            return await callback(c)
        wrapped.__name__='cb'; return old_reg(wrapped,*filters,**kwargs)
    a.r.callback_query.register=register; a._hold_mines_tower_router=True

def install(games):
    global _INSTALLED
    if _INSTALLED: return
    a=_ctx()
    if not a: return
    games._hold_activity={}; games._hold_timeout=300
    old_ms,old_ts=games.mines_start,games.tower_start
    old_mo,old_mc=games.mines_open,games.mines_cash
    old_tp,old_tc=games.tower_pick,games.tower_cash
    def ms(uid,bet,mines=3):
        _expired(games,'mines',uid); out=old_ms(uid,bet,mines)
        if out: games._hold_activity[('mines',uid)]=time.monotonic()
        return out
    def ts(uid,bet):
        _expired(games,'tower',uid); out=old_ts(uid,bet)
        if out: games._hold_activity[('tower',uid)]=time.monotonic()
        return out
    def mo(uid,i):
        if _expired(games,'mines',uid): return None
        out=old_mo(uid,i)
        if out and out[0]=='safe': games._hold_activity[('mines',uid)]=time.monotonic()
        elif out: games._hold_activity.pop(('mines',uid),None)
        return out
    def mc(uid):
        if _expired(games,'mines',uid): return None
        out=old_mc(uid); games._hold_activity.pop(('mines',uid),None); return out
    def tp(uid,col):
        if _expired(games,'tower',uid): return None
        out=old_tp(uid,col)
        if out and out[0] and out[2]<6: games._hold_activity[('tower',uid)]=time.monotonic()
        elif out: games._hold_activity.pop(('tower',uid),None)
        return out
    def tc(uid):
        if _expired(games,'tower',uid): return None
        out=old_tc(uid); games._hold_activity.pop(('tower',uid),None); return out
    games.mines_start=ms; games.tower_start=ts; games.mines_open=mo; games.mines_cash=mc; games.tower_pick=tp; games.tower_cash=tc
    games.cancel_game=lambda game,uid: _cancel(games,game,uid)
    try: threading.Thread(target=_loop,args=(games,),daemon=True,name='holdgame-mines-tower-timeout').start()
    except Exception: pass
    _install_router(a); _INSTALLED=True
