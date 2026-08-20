# Goldgame — FINAL

Telegram gambling/economy bot built with aiogram 3.

## Start on Windows

1. Copy `.env.example` to `.env`.
2. Put the BotFather token into `BOT_TOKEN`.
3. Put the two protected administrator Telegram IDs into `MASTER_ADMIN_IDS`, separated by a comma.
4. Open CMD in this folder and run:

```bat
cd /d E:\шлджен
python -m pip install -r requirements.txt
python bot.py
```

The database is created automatically as `goldcoin.db`.

## Included

- Telegram command menu with `/play` first.
- Main menu without a forced `/start` workflow.
- Basketball, football, darts and bowling use Telegram's real dice animations.
- Dice, Mines, 21, Tower, Coin, Bones and Spin.
- Bonus + cooldown, daily bonus, lottery, Free/Light/Express cases.
- Transfers, P2P gold → Goldcoin exchange with confirmation.
- Earn-by-subscription tasks.
- Profile, referral system, world top, promo codes, donation and editable rules.
- Admin panel: currencies/rate, bonuses, cases, promo codes, earn channels, donate/rules text, admins, give/take, broadcast, statistics.
- Two `MASTER_ADMIN_IDS` can add/remove ordinary admins.
- SQLite persistence.
