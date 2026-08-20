import os
import runpy
import site

# sitecustomize is not guaranteed to be imported when the script directory is
# added to sys.path after Python's site initialization. Import it explicitly.
try:
    import sitecustomize  # noqa: F401
except Exception as e:
    print(f'[KEYWORDS] sitecustomize load error: {e}')

runpy.run_path(os.path.join(os.path.dirname(__file__), 'bot.py'), run_name='__main__')
