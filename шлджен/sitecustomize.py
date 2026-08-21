"""Startup compatibility patch for the bot.

The project executes bot.py through start_bot.py with exec(compile(...)).
We keep the main bot source untouched here and make the remaining hard-coded
currency labels follow the database-configured currency names.
"""
import builtins
import os

_original_compile = builtins.compile


def _patched_compile(source, filename, mode, *args, **kwargs):
    if isinstance(source, str) and os.path.basename(str(filename)).lower() == 'bot.py':
        marker = "if __name__=='__main__':asyncio.run(main())"
        patch = r'''
# ---------- dynamic currency compatibility patch ----------
# Keep legacy database column names internally, but always display the
# currently configured currency names. If the old default names are still
# present, migrate them once to the project's current names.
try:
    if db.setting('primary_name') in (None, '', 'Goldcoin', 'goldcoin'):
        db.set_setting('primary_name', 'hCoin')
    if db.setting('premium_name') in (None, '', 'gold', 'Gold'):
        db.set_setting('premium_name', 'HPOINT')
except Exception:
    pass

_old_top_text = top_text

def top_text():
    rows = db.leaderboard(10)
    current = html.escape(currency_primary())
    lines = [f'<b>🏆 МИРОВОЙ ТОП ПО {current}</b>', '`'+SEP+'`']
    for i, u in enumerate(rows, 1):
        lines.append(f"{i}. {display_user(u)} | <code>{fmt(u['goldcoin'])}</code>")
    return '\n'.join(lines)

_old_admin_page = admin_page
async def admin_page(c, sec):
    if sec == 'currency':
        if not is_admin(c.from_user.id):
            return await c.answer('⛔ Нет доступа.', show_alert=True)
        uid = c.from_user.id
        txt = f"💰 <b>ВАЛЮТА И КУРС</b>\n`{SEP}`\n\nОсновная: <b>{currency_primary()}</b>\nДополнительная: <b>{currency_premium()}</b>\nКурс: <b>1 {currency_premium()} = {fmt(db.rate())} {currency_primary()}</b>\n\nОтправь одной строкой:\n<code>{currency_primary()} {currency_premium()} 45000</code>"
        state[uid] = {'admin':'currency'}
        return await show(c, txt, admin_k())
    if sec == 'money':
        if not is_admin(c.from_user.id):
            return await c.answer('⛔ Нет доступа.', show_alert=True)
        txt = f"💸 <b>ВЫДАТЬ / СПИСАТЬ</b>\n`{SEP}`\n\nВыдать: <code>/give @username {currency_primary()} 1000</code>\nСписать: <code>/take @username {currency_primary()} 1000</code>\n\nДоступны {currency_primary()} и {currency_premium()}."
        return await show(c, txt, admin_k())
    return await _old_admin_page(c, sec)
'''
        if marker in source and 'dynamic currency compatibility patch' not in source:
            source = source.replace(marker, patch + '\n' + marker, 1)
    return _original_compile(source, filename, mode, *args, **kwargs)


builtins.compile = _patched_compile
