import os
import runpy
import time
import traceback
import sys

# Load keyword support module before bot.py.
try:
    import sitecustomize  # noqa: F401
except Exception as e:
    print(f'[KEYWORDS] sitecustomize load error: {e}', flush=True)

# The old loader tried to inject the bank from Dispatcher.include_router().
# That happens BEFORE bot.py creates `db`, so the extension was never loaded.
# Instead, hook DB.__init__: bot.py creates DB before starting polling, and at
# that exact moment both the DB and Dispatcher already exist in __main__.
try:
    from database import DB as _DB
    _old_db_init = _DB.__init__
    _extensions_done = False

    def _db_init_with_extensions(self, *args, **kwargs):
        global _extensions_done
        _old_db_init(self, *args, **kwargs)
        if _extensions_done:
            return
        a = sys.modules.get('__main__') or sys.modules.get('bot')
        if a is None or not hasattr(a, 'dp'):
            print('[EXT] Dispatcher is not available yet.', flush=True)
            return
        try:
            if not hasattr(a, 'db'):
                a.db = self
            import bank_brand
            bank_brand.inject(a, a.dp, a.dp.include_router)
            try:
                import bank_keywords
                bank_keywords.inject(a, a.dp)
            except Exception as e:
                print(f'[EXT] keyword extension error: {e}', flush=True)
            _extensions_done = True
            print('[EXT] Bank + branding + keywords loaded.', flush=True)
        except Exception:
            print('[EXT] extension error during DB initialization:', flush=True)
            traceback.print_exc()

    _DB.__init__ = _db_init_with_extensions
except Exception:
    print('[EXT] DB extension loader error:', flush=True)
    traceback.print_exc()

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
