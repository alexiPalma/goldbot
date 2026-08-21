import os
import runpy
import time
import traceback
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(BASE, 'bot.py')

# The bank extension must be installed only AFTER bot.py has defined all
# handlers. Installing it from DB.__init__ was too early: at that moment
# group_keywords/state_input/callback handlers did not exist yet.
_injected = False

def _trace(frame, event, arg):
    global _injected
    if _injected:
        return None
    if event == 'line' and frame.f_globals.get('__name__') == '__main__':
        # bot.py reaches this line only after every function/handler has been
        # defined, but before asyncio.run(main()) starts polling.
        if frame.f_globals.get('main') is not None and frame.f_lineno >= 800:
            try:
                import bank_brand
                a = frame.f_globals
                # The actual bot module globals are exposed through __main__.
                bank_brand.inject(sys.modules['__main__'], a.get('dp'), a.get('dp').include_router if a.get('dp') else None)
                _injected = True
                sys.settrace(None)
                print('[EXT] Holdgame bank + keywords loaded.', flush=True)
            except Exception:
                print('[EXT] Bank extension error:', flush=True)
                traceback.print_exc()
                _injected = True
                sys.settrace(None)
    return _trace

while True:
    try:
        print('[BOT] Starting bot...', flush=True)
        _injected = False
        sys.settrace(_trace)
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
