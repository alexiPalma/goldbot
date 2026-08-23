import random
from decimal import Decimal

class Games:
    def __init__(self,db):
        self.db=db; self.mines={}; self.towers={}; self.blackjack={}
        try:
            from bot_extensions import install
            install(db)
        except Exception:
            pass
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
