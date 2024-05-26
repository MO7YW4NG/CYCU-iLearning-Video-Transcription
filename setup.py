from cx_Freeze import setup, Executable
import sys

# Set a higher recursion limit
sys.setrecursionlimit(20000)  # Adjust the value as needed
base = None

target = Executable(
    script="app.py",
    icon="icon.ico",
    base=base
)

setup(
    name="CYCU-iLearning-Video-Transcrption",
    version="1.0",
    description="cycu-ilearning-video-transcription",
    author="MO7YW4NG",
    options={'build_exe': {
        'packages': ['aiohttp','json','getpass','os','base64','time','asyncio','Crypto','bs4','whisper'],
        'include_files': ['icon.ico'],
        'excludes': ['zoneinfo'],
        "optimize": 2,
    }, 'bdist_msi': {'initial_target_dir': r'[DesktopFolder]\\CYCU-iLearning-Video-Transcrption'}},
    executables=[target],
)
