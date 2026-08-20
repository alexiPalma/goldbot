import os
import runpy
import site
import sys
import time
import traceback

# Explicitly load keyword routing before bot.py starts.
try:
    import sitecustomize  # noqa: F401
except Exception as e:
    print(f'[KEYWORDS] sitecustomize load error: {e}', flush=True)

BASE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(BASE, 'bot.py')

while True:
    try:
        print('[BOT] Starting bot...', flush=True)
        runpy.run_path(BOT, run_name='__main__')
        # A normal return from bot.py means there is no reason to exit silently.
        print('[BOT] Process ended. Restarting in 3 seconds...', flush=True)
    except KeyboardInterrupt:
        print('[BOT] Stopped by user.', flush=True)
        break
    except SystemExit as e:
        # Do not silently die on an unexpected SystemExit.
        print(f'[BOT] SystemExit: {e}. Restarting in 3 seconds...', flush=True)
    except Exception:
        print('[BOT] Unexpected crash. Full traceback:', flush=True)
        traceback.print_exc()
        print('[BOT] Restarting in 5 seconds...', flush=True)
        time.sleep(5)
        continue

    time.sleep(3)
