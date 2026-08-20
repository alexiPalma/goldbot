import sqlite3, time
from decimal import Decimal, InvalidOperation

class DB:
    def __init__(self, path='goldcoin.db'):
        self.path = path
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute('PRAGMA journal_mode=WAL')
        self.c.execute('PRAGMA foreign_keys=ON')
        self.init()

    def init(self):
        self.c.executescript('''
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
          goldcoin TEXT NOT NULL DEFAULT '0', gold TEXT NOT NULL DEFAULT '0',
          games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
          turnover TEXT DEFAULT '0', referrer INTEGER, referred_paid INTEGER DEFAULT 0,
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings_text(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,other_id INTEGER,
          kind TEXT,currency TEXT,amount TEXT,note TEXT,created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS cooldowns(user_id INTEGER,key TEXT,until_ts INTEGER,
          PRIMARY KEY(user_id,key));
        CREATE TABLE IF NOT EXISTS promo(
          code TEXT PRIMARY KEY,currency TEXT,amount TEXT,max_uses INTEGER,
          uses INTEGER DEFAULT 0,active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS promo_users(code TEXT,user_id INTEGER,PRIMARY KEY(code,user_id));
        CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY,title TEXT,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS earn_channels(
          id INTEGER PRIMARY KEY,title TEXT,username TEXT,chat_id INTEGER,
          active INTEGER DEFAULT 1,reward TEXT DEFAULT '1000'
        );
        CREATE TABLE IF NOT EXISTS games_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,game TEXT,bet TEXT,
          result TEXT,payout TEXT,win INTEGER DEFAULT 0,created_at INTEGER
        );
        ''')
        # Migrations for old DBs.
        cols = {r['name'] for r in self.c.execute('PRAGMA table_info(games_history)')}
        if 'win' not in cols:
            self.c.execute("ALTER TABLE games_history ADD COLUMN win INTEGER DEFAULT 0")
        cols = {r['name'] for r in self.c.execute('PRAGMA table_info(earn_channels)')}
        if 'chat_id' not in cols:
            self.c.execute("ALTER TABLE earn_channels ADD COLUMN chat_id INTEGER")
        defaults = {
            'primary_name':'Goldcoin', 'premium_name':'gold', 'rate':'1000000',
            'bonus_min':'100', 'bonus_max':'1000', 'bonus_cd':'3600',
            'daily_min':'1000', 'daily_max':'5000',
            'ref_reward':'15000', 'ref_loss_pct':'2',
            'light_price':'10000', 'express_price':'50000',
            'freecase_cd':'43200', 'lottery_cd':'86400',
            'earn_reward':'1000', 'earn_cd':'86400',
            'spin_multiplier':'5', 'sport_multiplier':'2', 'dice_multiplier':'6',
        }
        for k,v in defaults.items():
            self.c.execute('INSERT OR IGNORE INTO settings(k,v) VALUES(?,?)',(k,v))
        self.c.execute("INSERT OR IGNORE INTO settings_text(k,v) VALUES('donate',?)", (
            '💳 <b>ДОНАТ</b>\n`·····················`\n\nСвяжитесь с администрацией для пополнения.',))
        self.c.execute("INSERT OR IGNORE INTO settings_text(k,v) VALUES('rules',?)", (
            '📕 <b>ПРАВИЛА GOLDGAME</b>\n`·····················`\n\nСоблюдайте правила проекта и не злоупотребляйте механиками бота.',))
        self.c.commit()

    def setting(self,k):
        r=self.c.execute('SELECT v FROM settings WHERE k=?',(k,)).fetchone()
        return r['v'] if r else ''
    def set_setting(self,k,v):
        self.c.execute('INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',(k,str(v))); self.c.commit()
    def text(self,k):
        r=self.c.execute('SELECT v FROM settings_text WHERE k=?',(k,)).fetchone(); return r['v'] if r else ''
    def set_text(self,k,v):
        self.c.execute('INSERT INTO settings_text(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',(k,v)); self.c.commit()
    def rate(self): return Decimal(self.setting('rate') or '1000000')

    def user(self,uid,username=None,first_name=None):
        r=self.c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not r:
            self.c.execute('INSERT INTO users(id,username,first_name,created_at) VALUES(?,?,?,?)',(uid,username or '',first_name or 'Игрок',int(time.time())))
            self.c.commit(); r=self.c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        elif username is not None or first_name is not None:
            self.c.execute('UPDATE users SET username=COALESCE(?,username), first_name=COALESCE(?,first_name) WHERE id=?',(username,first_name,uid)); self.c.commit()
            r=self.c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        return r
    def find(self,ident):
        ident=(ident or '').strip()
        if ident.startswith('@'): ident=ident[1:]
        if ident.isdigit(): return self.user(int(ident)) if self.c.execute('SELECT 1 FROM users WHERE id=?',(int(ident),)).fetchone() else None
        return self.c.execute('SELECT * FROM users WHERE lower(username)=lower(?)',(ident,)).fetchone()
    def balance(self,uid):
        r=self.user(uid); return Decimal(r['goldcoin']),Decimal(r['gold'])
    def add(self,uid,currency,amount,kind='manual',other_id=None):
        try: amount=Decimal(str(amount))
        except InvalidOperation: return False
        if currency.lower()=='goldcoin': col='goldcoin'
        elif currency.lower()=='gold': col='gold'
        else: return False
        with self.c:
            r=self.c.execute(f'SELECT {col} FROM users WHERE id=?',(uid,)).fetchone()
            if not r: self.user(uid); r=self.c.execute(f'SELECT {col} FROM users WHERE id=?',(uid,)).fetchone()
            cur=Decimal(r[col]); new=cur+amount
            if new < 0: return False
            self.c.execute(f'UPDATE users SET {col}=? WHERE id=?',(str(new),uid))
            self.c.execute('INSERT INTO transactions(user_id,other_id,kind,currency,amount,note,created_at) VALUES(?,?,?,?,?,?,?)',(uid,other_id,kind,currency,str(amount),'',int(time.time())))
        return True
    def transfer(self,src,dst,currency,amount):
        try: amount=Decimal(str(amount))
        except InvalidOperation: return False,'Некорректная сумма.'
        if amount<=0:return False,'Сумма должна быть больше нуля.'
        if src==dst:return False,'Нельзя переводить самому себе.'
        cur=currency.lower()
        if cur not in ('goldcoin','gold'): return False,'Неизвестная валюта.'
        col='goldcoin' if cur=='goldcoin' else 'gold'
        label='Goldcoin' if cur=='goldcoin' else 'gold'
        self.user(dst)
        with self.c:
            s=self.c.execute(f'SELECT {col} FROM users WHERE id=?',(src,)).fetchone(); d=self.c.execute(f'SELECT {col} FROM users WHERE id=?',(dst,)).fetchone()
            if not s or not d or Decimal(s[col])<amount:return False,f'Недостаточно {label}.'
            self.c.execute(f'UPDATE users SET {col}=? WHERE id=?',(str(Decimal(s[col])-amount),src))
            self.c.execute(f'UPDATE users SET {col}=? WHERE id=?',(str(Decimal(d[col])+amount),dst))
            now=int(time.time())
            self.c.execute('INSERT INTO transactions(user_id,other_id,kind,currency,amount,note,created_at) VALUES(?,?,?,?,?,?,?)',(src,dst,'transfer_out',label,str(-amount),'',now))
            self.c.execute('INSERT INTO transactions(user_id,other_id,kind,currency,amount,note,created_at) VALUES(?,?,?,?,?,?,?)',(dst,src,'transfer_in',label,str(amount),'',now))
        return True,'OK'
    def record_game(self,uid,game,bet,result,payout,win):
        bet=Decimal(str(bet)); payout=Decimal(str(payout))
        self.c.execute('UPDATE users SET games=games+1,wins=wins+?,losses=losses+?,turnover=CAST(CAST(turnover AS REAL)+? AS TEXT) WHERE id=?',(int(bool(win)),int(not win),str(bet),uid))
        self.c.execute('INSERT INTO games_history(user_id,game,bet,result,payout,win,created_at) VALUES(?,?,?,?,?,?,?)',(uid,game,str(bet),result,str(payout),int(bool(win)),int(time.time())))
        self.c.commit()
    def user_rank(self,uid):
        r=self.c.execute("SELECT COUNT(*) n FROM users WHERE CAST(goldcoin AS REAL) > (SELECT CAST(goldcoin AS REAL) FROM users WHERE id=?)",(uid,)).fetchone(); return int(r['n'])+1
    def leaderboard(self,limit=10): return self.c.execute('SELECT * FROM users ORDER BY CAST(goldcoin AS REAL) DESC LIMIT ?',(limit,)).fetchall()
    def promos(self): return self.c.execute('SELECT * FROM promo ORDER BY code').fetchall()
    def create_promo(self,code,currency,amount,max_uses):
        self.c.execute('INSERT OR REPLACE INTO promo(code,currency,amount,max_uses,uses,active) VALUES(?,?,?,?,0,1)',(code.upper(),currency, str(amount),max_uses)); self.c.commit()
    def delete_promo(self,code): self.c.execute('UPDATE promo SET active=0 WHERE code=?',(code.upper(),)); self.c.commit()
    def use_promo(self,uid,code):
        code=code.strip().upper(); p=self.c.execute('SELECT * FROM promo WHERE code=? AND active=1',(code,)).fetchone()
        if not p:return False,'Промокод не найден или отключён.'
        if self.c.execute('SELECT 1 FROM promo_users WHERE code=? AND user_id=?',(code,uid)).fetchone():return False,'Ты уже использовал этот промокод.'
        if p['max_uses'] and p['uses']>=p['max_uses']:return False,'Лимит активаций промокода исчерпан.'
        self.user(uid)
        if not self.add(uid,p['currency'],Decimal(p['amount']),'promo') : return False,'Не удалось начислить награду.'
        with self.c:
            self.c.execute('INSERT INTO promo_users(code,user_id) VALUES(?,?)',(code,uid)); self.c.execute('UPDATE promo SET uses=uses+1 WHERE code=?',(code,))
        return True,f'+{p["amount"]} {p["currency"]}'
    def admins(self): return [r['id'] for r in self.c.execute('SELECT id FROM admins ORDER BY id').fetchall()]
    def add_admin(self,uid): self.c.execute('INSERT OR IGNORE INTO admins(id) VALUES(?)',(uid,)); self.c.commit()
    def del_admin(self,uid): self.c.execute('DELETE FROM admins WHERE id=?',(uid,)); self.c.commit()
    def cd_ready(self,uid,key): return self.cd_left(uid,key)<=0
    def cd_left(self,uid,key):
        r=self.c.execute('SELECT until_ts FROM cooldowns WHERE user_id=? AND key=?',(uid,key)).fetchone(); return max(0,(r['until_ts']-int(time.time())) if r else 0)
    def set_cd(self,uid,key,seconds): self.c.execute('INSERT INTO cooldowns(user_id,key,until_ts) VALUES(?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET until_ts=excluded.until_ts',(uid,key,int(time.time())+int(seconds))); self.c.commit()
    def group_ids(self): return [r['id'] for r in self.c.execute('SELECT id FROM groups WHERE active=1').fetchall()]
    def earn_channels(self): return self.c.execute('SELECT * FROM earn_channels WHERE active=1 ORDER BY id').fetchall()
    def stats(self):
        return {'users':self.c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'],'groups':self.c.execute('SELECT COUNT(*) n FROM groups WHERE active=1').fetchone()['n'],'tx':self.c.execute('SELECT COUNT(*) n FROM transactions').fetchone()['n'],'games':self.c.execute('SELECT COUNT(*) n FROM games_history').fetchone()['n']}
