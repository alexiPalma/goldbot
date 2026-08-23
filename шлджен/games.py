import asyncio
import random
import sys
from decimal import Decimal

class Games:
    def __init__(self,db):
        self.db=db; self.mines={}; self.towers={}; self.blackjack={}
        self._install_runtime_overrides()
        try:
            from bot_extensions_v2 import install
            install(db)
        except Exception:
            pass

    def _install_runtime_overrides(self):
        """Keep the legacy start_bot.py keyword layer compatible with the current game flow."""
        a=sys.modules.get('__main__')
        if not a or not hasattr(a,'r') or getattr(a,'_hold_runtime_overrides',False):
            return
        a._hold_runtime_overrides=True
        router=a.r

        # start_bot.py registers its legacy keyword handler at the very end and
        # moves it to the front. Wrap that registration so quick bets and custom
        # stake input are handled before the legacy handler can open only a menu.
        original_message_register=router.message.register
        def message_register(callback,*filters,**kwargs):
            if getattr(callback,'__name__','')=='_hold_keyword_handler':
                async def wrapped(message):
                    text=(message.text or '').strip()
                    uid=message.from_user.id
                    custom=getattr(a,'_hold_custom_bets',{})
                    if uid in custom and text and not text.startswith('/'):
                        try: amount=Decimal(text.replace("'",'').replace(',','.'))
                        except Exception:
                            custom.pop(uid,None)
                            return await message.answer('❌ Ставка должна быть положительным целым числом.')
                        if amount<=0 or amount!=amount.to_integral_value():
                            custom.pop(uid,None)
                            return await message.answer('❌ Ставка должна быть положительным целым числом.')
                        game=custom.pop(uid)
                        try:
                            from bot_extensions_v2 import _start_bet
                            return await _start_bet(uid,game,amount,message.chat.id,message)
                        except Exception:
                            import logging; logging.exception('custom stake')
                            return await message.answer('❌ Не удалось запустить игру. Попробуй ещё раз.')

                    parts=text.lower().split()
                    aliases={
                        'баскет':'basket','баскетбол':'basket','бск':'basket',
                        'фтб':'football','футбол':'football',
                        'дартс':'darts','дрс':'darts','дрт':'darts',
                        'кубик':'dice','куб':'dice',
                        'боулинг':'bowling','бол':'bowling','бл':'bowling',
                        'сп':'spin','спин':'spin',
                        'мины':'mines','мина':'mines',
                        '21':'21','очко':'21',
                        'башня':'tower','баш':'tower',
                        'монета':'coin','мон':'coin',
                        'кости':'dice2','кст':'dice2','кост':'dice2',
                    }
                    if len(parts)==2 and parts[0] in aliases:
                        try: amount=Decimal(parts[1].replace("'",'').replace(',','.'))
                        except Exception:
                            return await message.answer('❌ Укажи корректную ставку, например: <b>кости 30000</b>',parse_mode='HTML')
                        if amount<=0 or amount!=amount.to_integral_value():
                            return await message.answer('❌ Ставка должна быть положительным целым числом.')
                        try:
                            from bot_extensions_v2 import _start_bet
                            return await _start_bet(uid,aliases[parts[0]],amount,message.chat.id,message)
                        except Exception:
                            import logging; logging.exception('quick game')
                            return await message.answer('❌ Не удалось запустить игру. Попробуй ещё раз.')
                    return await callback(message)
                wrapped.__name__='_hold_keyword_handler'
                return original_message_register(wrapped,*filters,**kwargs)
            return original_message_register(callback,*filters,**kwargs)
        router.message.register=message_register

        # The old bot.py callback layer contains the old 1..6 dice-condition
        # keyboard and has no custom-stake button. Intercept its game/bet callbacks
        # and route them through the current universal game flow.
        original_callback_register=router.callback_query.register
        def callback_register(callback,*filters,**kwargs):
            if getattr(callback,'__name__','')=='cb':
                async def wrapped(c):
                    d=c.data or ''
                    uid=c.from_user.id
                    labels={
                        'basket':'🏀 Баскетбол','football':'⚽ Футбол','darts':'🎯 Дартс',
                        'dice':'🎲 Кубик','bowling':'🎳 Боулинг','spin':'🎰 Спин',
                        'mines':'💣 Мины','21':'🃏 21 очко','tower':'🗼 Башня',
                        'coin':'🪙 Монета','dice2':'🎲 Кости'
                    }
                    def bet_keyboard(game):
                        from aiogram.utils.keyboard import InlineKeyboardBuilder
                        b=InlineKeyboardBuilder()
                        for n in (10,100,1000,10000,100000):
                            b.button(text=f"{n:,}".replace(',','\''),callback_data=f'holdbet:{game}:{n}')
                        b.button(text='✍️ Своя ставка',callback_data=f'holdcustom:{game}')
                        b.button(text='◀️ Назад',callback_data='play')
                        b.adjust(2,2,1,1,1)
                        return b.as_markup()
                    def dice2_keyboard(amount):
                        from aiogram.utils.keyboard import InlineKeyboardBuilder
                        b=InlineKeyboardBuilder()
                        for n in range(2,6):
                            b.button(text=f'Меньше {n}',callback_data=f'holdcond:lt:{n}:{amount}')
                            b.button(text=f'Равно {n}',callback_data=f'holdcond:eq:{n}:{amount}')
                            b.button(text=f'Больше {n}',callback_data=f'holdcond:gt:{n}:{amount}')
                        b.button(text='◀️ Назад',callback_data='play'); b.adjust(3,3,3,3,1)
                        return b.as_markup()

                    if d.startswith('game:'):
                        game=d.split(':',1)[1]
                        if game in labels:
                            await c.answer()
                            return await a.show(c,f"{labels[game]}\n`{a.SEP}`\n\nВыбери ставку:",bet_keyboard(game))
                    if d.startswith('bet:'):
                        try:
                            _,game,amount=d.split(':',2)
                            if game=='dice2':
                                await c.answer()
                                return await a.show(c,f"🎲 <b>КОСТИ</b>\n`{a.SEP}`\n\nВыбери условие и число <b>от 2 до 5</b>:\n\nСтавка: <b>{amount} {a.currency_primary()}</b>",dice2_keyboard(amount))
                        except Exception:
                            pass
                    if d.startswith('holdbet:'):
                        _,game,amount=d.split(':',2)
                        await c.answer()
                        try:
                            from bot_extensions_v2 import _start_bet
                            return await _start_bet(uid,game,Decimal(amount),c.message.chat.id,c.message)
                        except Exception:
                            import logging; logging.exception('holdbet')
                            return await c.answer('❌ Не удалось запустить игру.',show_alert=True)
                    if d.startswith('holdcustom:'):
                        game=d.split(':',1)[1]
                        await c.answer()
                        custom=getattr(a,'_hold_custom_bets',None)
                        if custom is None: custom={}; setattr(a,'_hold_custom_bets',custom)
                        custom[uid]=game
                        return await a.show(c,f"✍️ <b>СВОЯ СТАВКА</b>\n`{a.SEP}`\n\nВведи сумму ставки для <b>{labels.get(game,'игры')}</b> одним сообщением.\n\nНапример: <code>30000</code>",a.one_back('play'))
                    if d.startswith('holdcond:'):
                        _,op,target,amount=d.split(':',3)
                        await c.answer()
                        try:
                            from bot_extensions_v2 import _dicecond
                            return await _dicecond(c,uid,op,int(target),Decimal(amount))
                        except Exception:
                            import logging; logging.exception('holdcond')
                            return await c.answer('❌ Не удалось запустить кости.',show_alert=True)
                    return await callback(c)
                wrapped.__name__='cb'
                return original_callback_register(wrapped,*filters,**kwargs)
            return original_callback_register(callback,*filters,**kwargs)
        router.callback_query.register=callback_register

    def cost(self,uid,bet,kind):
        bet=Decimal(str(bet)); return bet>0 and self.db.add(uid,'Goldcoin',-bet,kind)
    def finish(self,uid,game,bet,result,payout,win):
        payout=Decimal(str(payout))
        if payout>0:self.db.add(uid,'Goldcoin',payout,game+'_win')
        self.db.record_game(uid,game,bet,result,payout,win); return payout
    def sports(self,uid,game,bet,value):
        if not self.cost(uid,bet,game+'_bet'):return None
        win = value in ({'basket':{4,5},'football':{3,4,5},'bowling':{6},'darts':{6}}[game])
        payout=Decimal(bet)*Decimal(self.db.setting('sport_multiplier') or '2') if win else Decimal(0)
        self.finish(uid,game,bet,'hit' if win else 'miss',payout,win); return win,payout
    def spin(self,uid,bet):
        if not self.cost(uid,bet,'spin_bet'):return None
        symbols=['🍒','🍋','🍉','🍇','⭐','7️⃣']; reels=[random.choice(symbols) for _ in range(3)]
        win=len(set(reels))==1; payout=Decimal(bet)*Decimal(self.db.setting('spin_multiplier') or '5') if win else Decimal(0)
        self.finish(uid,'spin',bet,'three_equal' if win else 'no_combo',payout,win); return reels,payout
    def dice_guess(self,uid,bet,guess):
        if not self.cost(uid,bet,'dice_bet'):return None
        v=random.randint(1,6); win=v==guess; payout=Decimal(bet)*Decimal(self.db.setting('dice_multiplier') or '6') if win else Decimal(0)
        self.finish(uid,'dice',bet,f'guess:{guess};roll:{v}',payout,win); return v,payout,win
    def dice_condition(self,uid,bet,op,target):
        target=int(target)
        if target<2 or target>5:return None
        if not self.cost(uid,bet,'dice2_bet'):return None
        v=random.randint(1,6); win={'lt':v<target,'eq':v==target,'gt':v>target}[op]; payout=Decimal(bet)*Decimal('1.8') if win else Decimal(0)
        self.finish(uid,'dice2',bet,f'{op}:{target};roll:{v}',payout,win); return v,payout,win
    def coin(self,uid,bet,choice):
        if not self.cost(uid,bet,'coin_bet'):return None
        v=random.choice(['Орёл','Решка']); win=v==choice; payout=Decimal(bet)*2 if win else Decimal(0)
        self.finish(uid,'coin',bet,v,payout,win); return v,payout,win
    def tower_start(self,uid,bet):
        if uid in self.towers or not self.cost(uid,bet,'tower_bet'):return False
        self.towers[uid]={'bet':Decimal(bet),'floor':1,'bombs':{i:random.randrange(3) for i in range(1,7)}}; return True
    def tower_pick(self,uid,col):
        g=self.towers.get(uid)
        if not g:return None
        f=g['floor']
        if col==g['bombs'][f]:
            self.towers.pop(uid); self.db.record_game(uid,'tower',g['bet'],f'bomb:{f}',0,False); return False,0,f
        p=(g['bet']*Decimal('1.35')**f).quantize(Decimal('1'))
        if f>=6:self.towers.pop(uid); self.finish(uid,'tower',g['bet'],'finish',p,True); return True,p,f
        g['floor']+=1; return True,p,f
    def tower_cash(self,uid):
        g=self.towers.pop(uid,None)
        if not g:return None
        p=(g['bet']*Decimal('1.35')**(g['floor']-1)).quantize(Decimal('1')); self.finish(uid,'tower',g['bet'],'cashout',p,True); return p
    def mines_start(self,uid,bet,mines=3):
        if uid in self.mines or not self.cost(uid,bet,'mines_bet'):return False
        self.mines[uid]={'bet':Decimal(bet),'mines':set(random.sample(range(25),mines)),'opened':set(),'mult':Decimal('1')}; return True
    def mines_open(self,uid,i):
        g=self.mines.get(uid)
        if not g:return None
        if i in g['opened']:return 'opened',g
        if i in g['mines']:
            self.mines.pop(uid); self.db.record_game(uid,'mines',g['bet'],'bomb',0,False); return 'bomb',g
        g['opened'].add(i); g['mult']*=Decimal('1.18'); return 'safe',g
    def mines_cash(self,uid):
        g=self.mines.pop(uid,None)
        if not g:return None
        p=(g['bet']*g['mult']).quantize(Decimal('1')); self.finish(uid,'mines',g['bet'],'cashout',p,True); return p
    def blackjack_start(self,uid,bet):
        if uid in self.blackjack or not self.cost(uid,bet,'21_bet'):return False
        deck=list('23456789')+['10']*4+['J','Q','K','A']
        self.blackjack[uid]={'bet':Decimal(bet),'player':[random.choice(deck),random.choice(deck)],'dealer':[random.choice(deck),random.choice(deck)]}; return self.blackjack[uid]
    @staticmethod
    def hand(cards):
        vals={'J':10,'Q':10,'K':10,'A':11}; s=0; aces=0
        for c in cards:
            s += vals[c] if c in vals else int(c)
            aces += c=='A'
        while s>21 and aces:s-=10; aces-=1
        return s
    def blackjack_hit(self,uid):
        g=self.blackjack.get(uid)
        if not g:return None
        deck=list('23456789')+['10']*4+['J','Q','K','A']; g['player'].append(random.choice(deck)); return g
    def blackjack_stop(self,uid):
        g=self.blackjack.pop(uid,None)
        if not g:return None
        deck=list('23456789')+['10']*4+['J','Q','K','A']
        while self.hand(g['dealer'])<17:g['dealer'].append(random.choice(deck))
        p,d=self.hand(g['player']),self.hand(g['dealer']); win=p<=21 and (d>21 or p>d); tie=p==d and p<=21
        payout=g['bet']*2 if win else g['bet'] if tie else 0
        self.finish(uid,'21',g['bet'],'win' if win else 'tie' if tie else 'loss',payout,win); return g,p,d,payout,win,tie
    def lottery(self,uid):
        if not self.db.cd_ready(uid,'lottery'):return None
        self.db.set_cd(uid,'lottery',int(self.db.setting('lottery_cd') or 86400)); p=[10000,100,3000]+[0]*7; random.shuffle(p); return p
    def free_case_start(self,uid):
        if not self.db.cd_ready(uid,'freecase'):return False
        self.db.set_cd(uid,'freecase',int(self.db.setting('freecase_cd') or 43200)); return True
