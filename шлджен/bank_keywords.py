import sys
from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router(name='gold_bank_keywords')

def app():
    return sys.modules.get('__main__') or sys.modules.get('bot')

def _add_button(markup, text, data):
    if not markup:
        return markup
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == data:
                return markup
    b = InlineKeyboardBuilder()
    for row in markup.inline_keyboard:
        b.row(*row)
    b.button(text=text, callback_data=data)
    return b.as_markup()

def inject(a, dp):
    if getattr(dp, '_gold_bank_keywords', False):
        return
    dp.include_router(router)
    dp._gold_bank_keywords = True

    # Patch main menu after bot.py has finished defining main_k.
    async def on_startup(*args, **kwargs):
        mod = app()
        if mod is None or not hasattr(mod, 'main_k'):
            return
        old_main = mod.main_k
        if getattr(old_main, '_gold_bank_wrapped', False):
            return
        def main_k_with_bank(uid):
            markup = old_main(uid)
            return _add_button(markup, '🏦 Банк', 'bank')
        main_k_with_bank._gold_bank_wrapped = True
        mod.main_k = main_k_with_bank
    dp.startup.register(on_startup)

@router.message(F.text.func(lambda x: (x or '').strip().lower() == 'банк'))
async def bank_keyword(m):
    a = app()
    if a is None or not hasattr(a, 'state'):
        return
    # Respect active multi-step dialogs.
    if a.state.get(m.from_user.id):
        return
    await m.answer('🏦 <b>БАНК</b>\n\nОткрываю банк...', parse_mode='HTML')
    # Reuse the real bank callback handler by sending the same UI directly.
    try:
        from bank_brand import bank_text, bank_markup
        a.db.user(m.from_user.id, m.from_user.username, m.from_user.first_name)
        await m.answer(bank_text(a, m.from_user.id), reply_markup=bank_markup(a, m.from_user.id), parse_mode='HTML')
    except Exception as e:
        await m.answer(f'❌ Не удалось открыть банк: {e}')
