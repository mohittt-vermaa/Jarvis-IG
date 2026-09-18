#!/usr/bin/env python3
r"""
===========================================================
  Mohit's Instagram Auto-Reply Bot — TERMUX / ANDROID / PC
===========================================================
SUPER EASY SETUP — no editing required. When you run it for
the first time, it will ASK YOU for your username & password
right in the terminal, then save them so you don't have to
enter them again.

-----------------------------------------------------------
  COPY-PASTE THESE COMMANDS IN TERMUX (one by one):
-----------------------------------------------------------
    pkg update -y && pkg upgrade -y
    pkg install python python-pillow libjpeg-turbo -y
    rm -f ig_bot.py
    curl -o ig_bot.py https://raw.githubusercontent.com/mohittt-vermaa/Jarvis-IG/main/jarvis_ig/ig_bot.py
    python ig_bot.py

Then just answer the prompts it shows you. Done.
On PC/Mac/Linux it works the same way (just install Python + Pillow first).
"""

import sys, os, subprocess, getpass, json
from pathlib import Path

CONFIG_FILE = Path.home() / ".ig_bot_config.json"
SESSION_FILE = Path.home() / ".ig_session_mohit.json"


# ---------- install missing dependencies automatically ----------
def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

def ensure_deps():
    # Pillow on Termux must come from pkg install python-pillow
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print(">>> Pillow not found. On Termux run:")
        print("    pkg install python-pillow -y")
        print("    On PC: pip install Pillow")
        sys.exit(1)

    # Pure-Python helper libs
    for mod, pip_name in [
        ("requests", "requests"),
        ("socks", "PySocks"),
        ("Cryptodome", "pycryptodomex"),
        ("typing_extensions", "typing_extensions"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            print(f">>> Installing {pip_name}...")
            install(pip_name)

    # pydantic v1 (pure Python, no Rust needed — works on Termux Python 3.13)
    need_pydantic = False
    try:
        import pydantic
        if int(pydantic.__version__.split(".")[0]) >= 2:
            need_pydantic = True
    except ImportError:
        need_pydantic = True
    if need_pydantic:
        print(">>> Installing pydantic v1 (Termux-friendly)...")
        install("pydantic<2")

    try:
        import instagrapi  # noqa: F401
    except ImportError:
        print(">>> Installing instagrapi...")
        install("instagrapi==2.1.2")


ensure_deps()

from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired,
    ChallengeRequired,
    TwoFactorRequired,
    PleaseWaitFewMinutes,
)


# ---------- super easy credentials: ask in terminal on first run ----------
def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            if cfg.get("username") and cfg.get("password"):
                return cfg
        except Exception:
            pass
    return {}


def ask_config():
    print()
    print("=" * 56)
    print("  FIRST TIME SETUP")
    print("  Please enter your Instagram login details.")
    print("  (Your password stays on YOUR phone — it is saved")
    print("   only to the hidden file ~/.ig_bot_config.json)")
    print("=" * 56)
    while True:
        username = input("Instagram username (without @): ").strip().lstrip("@")
        if username:
            break
        print("Please type your username.")
    while True:
        password = getpass.getpass("Instagram password: ").strip()
        if password:
            break
        print("Please type your password.")
    msg_default = (
        "Hey! Thanks for messaging me.\n"
        "This is Mohit's auto-reply bot — I'll get back to you personally very soon!"
    )
    print()
    print(f"Auto-reply message (press Enter to use the default):")
    print(f"  > {msg_default}")
    custom_msg = input("Custom message (or Enter for default): ").strip()
    message = custom_msg if custom_msg else msg_default

    cfg = {
        "username": username,
        "password": password,
        "auto_reply": message,
        "only_new_threads": True,
        "poll_interval": 20,
        "delay_min": 4,
        "delay_max": 12,
    }
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        print(f"\n>>> Saved! You can edit later by running: nano {CONFIG_FILE}")
    except Exception as e:
        print(f"\n>>> Note: could not save config ({e}); you'll be asked again next run.")
    return cfg


def reset_config():
    if CONFIG_FILE.exists():
        try:
            CONFIG_FILE.unlink()
        except Exception:
            pass


# If user passes --reset flag, wipe saved config first
if "--reset" in sys.argv or "-r" in sys.argv:
    reset_config()
    print(">>> Cleared saved login info. Will ask for fresh details.")

cfg = load_config()
if not cfg:
    cfg = ask_config()

USERNAME             = cfg["username"]
PASSWORD             = cfg["password"]
AUTO_REPLY_MESSAGE   = cfg.get("auto_reply")
REPLY_ONLY_NEW       = cfg.get("only_new_threads", True)
POLL_INTERVAL        = int(cfg.get("poll_interval", 20))
DELAY_MIN            = int(cfg.get("delay_min", 4))
DELAY_MAX            = int(cfg.get("delay_max", 12))

if not AUTO_REPLY_MESSAGE:
    AUTO_REPLY_MESSAGE = (
        "Hey! Thanks for messaging me. "
        "This is Mohit's auto-reply bot — I'll get back to you personally very soon!"
    )


cl = Client()
cl.delay_range = [DELAY_MIN, DELAY_MAX]
seen_threads: set = set()


def save_session():
    try:
        SESSION_FILE.write_text(cl.get_settings())
    except Exception:
        pass


def load_session():
    if SESSION_FILE.exists():
        try:
            cl.load_settings(str(SESSION_FILE))
            return True
        except Exception:
            pass
    return False


def login():
    if load_session():
        try:
            cl.login(USERNAME, PASSWORD)
            print(f"[ok] Logged in as @{USERNAME} (saved session).")
            return
        except Exception:
            print("[session] Saved session expired; logging in fresh...")
    try:
        cl.login(USERNAME, PASSWORD)
    except TwoFactorRequired:
        code = input("[2fa] Enter the 6-digit code from SMS/Auth app: ").strip()
        cl.login(USERNAME, PASSWORD, verification_code=code)
    except ChallengeRequired:
        print("[challenge] Instagram needs a security check.")
        print("            Open Instagram app -> 'Was this you?' -> Approve it.")
        input("            Press Enter AFTER you approved, then I'll continue...")
        try:
            cl.login(USERNAME, PASSWORD)
        except Exception:
            pass
    except Exception as e:
        print(f"[login] {type(e).__name__}: {e}")
        print("         -> Wrong password/2FA code? Run with --reset to re-enter:")
        print("              python ig_bot.py --reset")
        sys.exit(1)
    save_session()
    print(f"[ok] Logged in as @{USERNAME}!")


def reply_loop():
    print()
    print("=" * 62)
    print("  Mohit's IG Auto-Reply is LIVE  (Ctrl+C to stop)")
    print(f"  Reply message    : {AUTO_REPLY_MESSAGE[:80]}{'...' if len(AUTO_REPLY_MESSAGE) > 80 else ''}")
    print(f"  New threads only : {REPLY_ONLY_NEW}")
    print(f"  Check interval   : {POLL_INTERVAL}s")
    print("  To change login later, run:  python ig_bot.py --reset")
    print("=" * 62)
    print()

    while True:
        try:
            threads = cl.direct_threads(amount=20)
            for t in threads:
                if not getattr(t, "messages", None):
                    continue
                last = t.messages[0]
                key = f"{t.id}:{last.id}"
                if key in seen_threads:
                    continue
                me_id = cl.user_id
                if str(getattr(last, "user_id", "")) == str(me_id):
                    seen_threads.add(key)
                    continue
                if REPLY_ONLY_NEW and len(t.messages) != 1:
                    seen_threads.add(key)
                    continue

                seen_threads.add(key)
                sender = last.user_id
                sender_name = "someone"
                try:
                    for u in t.users:
                        if str(u.pk) == str(sender):
                            sender_name = u.username
                            break
                except Exception:
                    pass
                preview = (last.text or "[media/sticker]")[:60]
                print(f"[dm] New DM from @{sender_name}: {preview}")
                try:
                    cl.direct_send(AUTO_REPLY_MESSAGE, thread_ids=[t.id])
                    print("     -> Auto-reply sent.")
                except Exception as e:
                    print(f"     !! Could not send reply: {e}")

            time.sleep(POLL_INTERVAL)
        except PleaseWaitFewMinutes:
            print("[rate] Instagram asked us to slow down; sleeping 10 minutes...")
            time.sleep(600)
        except LoginRequired:
            print("[auth] Session expired; logging back in...")
            try:
                login()
            except Exception:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n[stop] Bot stopped. Goodbye!")
            break
        except Exception as e:
            print(f"[error] {type(e).__name__}: {e}")
            time.sleep(30)


if __name__ == "__main__":
    print("=" * 62)
    print("   MOHIT's IG AUTO-REPLY BOT   (Termux / Phone / PC)")
    print("=" * 62)
    login()
    reply_loop()
