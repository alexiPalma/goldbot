import os
import runpy
import time
import traceback

# Explicitly load keyword routing before bot.py starts.
try:
    import sitecustomize  # noqa: F401
except Exception as e:
    print(f'[KEYWORDS] sitecustomize load error: {e}', flush=True)

# Inject extensions only after bot.py has created its DB object.
try:
    from aiogram import Dispatcher
    _old_include = Dispatcher.include_router

    def _include_with_extensions(self, router):
        result = _old_include(self, router)
        if not getattr(self, '_gold_extensions_loaded', False):
            import sys
            a = sys.modules.get('__main__') or sys.modules.get('bot')
            if a is not None and hasattr(a, 'DB'):
                try:
                    if not hasattr(a, 'db'):
                        a.db = a.DB
                    import bank_brand
                    bank_brand.inject(a, self, _old_include)
                    import bank_keywords
                    bank_keywords.inject(a, self)
                    self._gold_extensions_loaded = True
                    print('[EXT] Bank + branding loaded.', flush=True)
                except Exception as e:
                    print(f'[EXT] extension error: {e}', flush=True)
        return result

    Dispatcher.include_router = _include_with_extensions
except Exception as e:
    print(f'[EXT] extension loader error: {e}', flush=True)

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
