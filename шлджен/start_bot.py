import os
import runpy
import time
import traceback

# Explicitly load keyword routing before bot.py starts.
try:
    import sitecustomize  # noqa: F401
except Exception as e:
    print(f'[KEYWORDS] sitecustomize load error: {e}', flush=True)

# Inject bank/branding only after bot.py has created its DB object.
# The previous implementation injected during the first include_router call,
# which happens before DB is assigned in bot.py and caused AttributeError.
try:
    from aiogram import Dispatcher
    _old_include = Dispatcher.include_router
    _patched = False

    def _include_with_bank(self, router):
        global _patched
        result = _old_include(self, router)
        if not getattr(self, '_gold_bank_router', False):
            import sys
            a = sys.modules.get('__main__') or sys.modules.get('bot')
            # bot.py has created DB by the time it reaches its first
            # include_router call, so use the actual DB global (and alias it
            # as db for the extension's API).
            if a is not None and hasattr(a, 'DB'):
                try:
                    if not hasattr(a, 'db'):
                        a.db = a.DB
                    import bank_brand
                    bank_brand.inject(a, self, _old_include)
                    self._gold_bank_router = True
                except Exception as e:
                    print(f'[BANK] extension error: {e}', flush=True)
        return result

    Dispatcher.include_router = _include_with_bank
except Exception as e:
    print(f'[BANK] extension load error: {e}', flush=True)

BASE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(BASE, 'bot.py')

while True:
    try:
        print('[BOT] Starting bot...', flush=True)
        runpy.run_path(BOT, run_name='__main__')
        print('[BOT] Process ended. Restarting in 3 seconds...', flush=True)
    except KeyboardInterrupt:
        print('[BOT] Stopped by user.', flush=True)
        break
    except SystemExit as e:
        print(f'[BOT] SystemExit: {e}. Restarting in 3 seconds...', flush=True)
    except Exception:
        print('[BOT] Unexpected crash. Full traceback:', flush=True)
        traceback.print_exc()
        print('[BOT] Restarting in 5 seconds...', flush=True)
        time.sleep(5)
        continue
    time.sleep(3)
