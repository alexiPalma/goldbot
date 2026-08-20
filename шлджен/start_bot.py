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

# Bank extension must be installed after DB exists, while bot.py is still
# being defined. Hook DB.__init__ for the router/database part.
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
            return
        try:
            if not hasattr(a, 'db'):
                a.db = self
            import bank_brand
            bank_brand.inject(a, a.dp, a.dp.include_router)
            import bank_keywords
            bank_keywords.inject(a, a.dp)
            _extensions_done = True
            print('[EXT] Bank database/router loaded.', flush=True)
        except Exception:
            print('[EXT] extension error during DB initialization:', flush=True)
            traceback.print_exc()

    _DB.__init__ = _db_init_with_extensions
except Exception:
    print('[EXT] DB extension loader error:', flush=True)
    traceback.print_exc()

# bot.py defines main_k() AFTER DB initialization. Therefore a normal import
# hook cannot safely replace it at that point. This trace watches only until
# main_k appears, wraps it once, then removes itself. This guarantees the
# actual /start menu contains the Bank button regardless of startup timing.
_trace_done = False

def _inject_bank_menu(frame, event, arg):
    global _trace_done
    if _trace_done:
        return None
    if event == 'line' and frame.f_globals.get('__name__') == '__main__':
        fn = frame.f_globals.get('main_k')
        if callable(fn) and not getattr(fn, '_gold_bank_wrapped', False):
            try:
                import bank_keywords
                old = fn
                def main_k_with_bank(uid):
                    markup = old(uid)
                    return bank_keywords._add_button(markup, '🏦 Банк', 'bank')
                main_k_with_bank._gold_bank_wrapped = True
                frame.f_globals['main_k'] = main_k_with_bank
                _trace_done = True
                sys.settrace(None)
                print('[EXT] Bank button injected into main menu.', flush=True)
            except Exception:
                print('[EXT] main menu injection error:', flush=True)
                traceback.print_exc()
                _trace_done = True
                sys.settrace(None)
    return _inject_bank_menu

sys.settrace(_inject_bank_menu)

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
