"""
Anti-Spam Shield for GetMeCare Contact Form

Provides a multi-layered barrier against spam bots:
1. Dynamic cryptographic math challenge (HMAC-signed with Django SECRET_KEY).
2. Deceptive hidden honeypots (irresistible to automated scripts).
3. Minimum submission time gate (rejects headless bots submitting in < 3s).
4. Content heuristic filters (detects BBCode, excessive URLs, Cyrillic, casino/crypto/SEO spam).
5. Automatic 48-hour IP banning on repeated abuse.
"""

import re
import time
import hashlib
import random
from django.core import signing
from django.core.cache import cache

SALT = 'gmc-contact-antispam-shield'

# Known spam keywords (case-insensitive substring matches)
SPAM_KEYWORDS = [
    'viagra', 'cialis', 'casino', 'poker', 'crypto', 'bitcoin', 'ethereum',
    'binance', 'telegram:', 't.me/', 'whatsapp: +7', 'seo service', 'backlink',
    'guest post', 'ranking on google', 'first page of google', 'porn', 'dating site',
    'adult chat', 'quick loan', 'earn $', 'make money fast', 'investment opportunity',
    'airdrop', 'forex trading', 'financial freedom', 'whatsapp me on', 'sex video'
]

# High-risk TLDs commonly abused in bot spam
HIGH_RISK_TLDS = ['.ru', '.su', '.cn', '.top', '.xyz', '.work', '.click', '.gq', '.ml', '.cf', '.tk']


def get_client_ip(request) -> str:
    """Extract reliable client IP from headers."""
    raw = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR', '')
    return raw.split(',')[0].strip() or '127.0.0.1'


def is_ip_banned(ip: str) -> bool:
    """Check if the IP is currently banned."""
    key = 'banned_ip_' + hashlib.md5(ip.encode()).hexdigest()
    return bool(cache.get(key))


def ban_ip(ip: str, hours: int = 48):
    """Ban an abusive IP address in cache."""
    key = 'banned_ip_' + hashlib.md5(ip.encode()).hexdigest()
    cache.set(key, True, timeout=hours * 3600)


def record_strike(ip: str):
    """Record an anti-spam violation strike; ban after 3 strikes."""
    key = 'strikes_ip_' + hashlib.md5(ip.encode()).hexdigest()
    strikes = cache.get(key, 0) + 1
    cache.set(key, strikes, timeout=3600)
    if strikes >= 3:
        ban_ip(ip, hours=48)


def generate_contact_challenge():
    """
    Generate two single-digit numbers for a human math challenge
    and sign the payload with timestamp.
    """
    n1 = random.randint(2, 9)
    n2 = random.randint(1, 9)
    ans = n1 + n2
    token = signing.dumps({'ans': ans, 'ts': int(time.time())}, salt=SALT)
    return n1, n2, token


def check_contact_submission(request):
    """
    Runs full anti-spam verification pipeline.
    
    Returns:
        (is_valid: bool, error_message: str, is_honeypot_bot: bool)
    """
    ip = get_client_ip(request)

    # 1. IP Ban check
    if is_ip_banned(ip):
        return False, "Your network has been temporarily blocked due to unusual activity. Please contact info@getmecare-ontario.com.", False

    # 2. Deceptive Honeypots check (bots automatically fill these)
    hp_fields = ['website', 'company_website', 'business_title']
    for hp in hp_fields:
        if request.POST.get(hp, '').strip():
            record_strike(ip)
            # Flagged as bot -> silent fake success
            return False, "", True

    # 3. Cryptographic Math Challenge + Timing
    token = request.POST.get('captcha_token', '').strip()
    user_ans = request.POST.get('captcha_ans', '').strip()

    if not token or not user_ans:
        record_strike(ip)
        return False, "Please solve the anti-spam security check before submitting.", False

    try:
        data = signing.loads(token, salt=SALT, max_age=7200)  # valid for 2 hours
        expected_ans = data.get('ans')
        loaded_ts = data.get('ts', 0)
    except (signing.BadSignature, signing.SignatureExpired):
        return False, "Security verification expired. Please refresh the page and try again.", False

    # Timing check: humans need at least 3 seconds to read and fill the form
    elapsed = int(time.time()) - loaded_ts
    if elapsed < 3:
        record_strike(ip)
        return False, "", True  # Headless bot filled in < 3s -> silent discard

    # Answer check
    try:
        if int(user_ans) != int(expected_ans):
            record_strike(ip)
            return False, "Incorrect security answer. Please solve the simple math check and try again.", False
    except (ValueError, TypeError):
        record_strike(ip)
        return False, "Please enter a valid numeric answer for the security check.", False

    # 4. Content Heuristics Check
    subject = request.POST.get('subject', '')
    message = request.POST.get('message', '')
    email = request.POST.get('email', '')
    combined = f"{subject} {message} {email}".lower()

    # Reject BBCode and raw HTML tags
    if re.search(r'\[url=|<a\s|\[link=|<script|<\/script>', combined):
        record_strike(ip)
        return False, "", True

    # Check for excessive links (> 1 URL is almost always spam on a care inquiry)
    urls = re.findall(r'https?://[^\s]+', combined)
    if len(urls) > 1:
        record_strike(ip)
        return False, "For security, messages with multiple web links are not allowed. Please describe your request directly.", False

    # Check for high-risk TLDs
    for tld in HIGH_RISK_TLDS:
        if tld in combined:
            record_strike(ip)
            return False, "", True

    # Check for excessive Cyrillic characters (Russian spam bots)
    cyrillic_count = len(re.findall(r'[\u0400-\u04FF]', subject + message))
    if cyrillic_count > 4:
        record_strike(ip)
        return False, "", True

    # Check for known spam keywords
    for kw in SPAM_KEYWORDS:
        if kw in combined:
            record_strike(ip)
            return False, "Your message triggered our automated security filter. Please revise your inquiry or email us directly.", False

    return True, "", False
