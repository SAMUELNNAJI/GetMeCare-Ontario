#!/usr/bin/env bash
# ============================================================
#  One-time VPS setup script for GetMeCare on TrueHost
#
#  Run this ONCE on a fresh VPS as root (or with sudo):
#    bash /path/to/setup.sh
#
#  What it does:
#   1. Installs system packages (nginx, python3, certbot, etc.)
#   2. Creates the 'getmecare' system user
#   3. Creates a bare Git repo the you push to
#   4. Installs the post-receive deploy hook
#   5. Clones/checks out your app for the first time
#   6. Creates and activates a Python virtualenv
#   7. Installs the Gunicorn systemd service
#   8. Installs and enables the Nginx site config
#   9. Opens firewall ports
# ============================================================
set -euo pipefail

# ── Edit these before running ────────────────────────────────
DOMAIN="yourdomain.com"                  # your real domain
GIT_REPO_URL="git@github.com:YOU/REPO.git"  # your GitHub repo URL
APP_USER="getmecare"
APP_DIR="/home/$APP_USER/app"
REPO_DIR="/home/$APP_USER/repo.git"
LOG_DIR="/var/log/getmecare"
GUNICORN_SERVICE="gunicorn-getmecare"
# ────────────────────────────────────────────────────────────

echo "====================================================="
echo "  GetMeCare — TrueHost VPS setup"
echo "====================================================="

# ── 1. System packages ───────────────────────────────────────
echo "[1] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    nginx \
    python3 python3-pip python3-venv python3-dev \
    build-essential libpq-dev \
    git curl ufw \
    certbot python3-certbot-nginx

# ── 2. Create app user ───────────────────────────────────────
echo "[2] Creating app user '$APP_USER'..."
id -u "$APP_USER" &>/dev/null || useradd --system --shell /bin/bash \
    --home "/home/$APP_USER" --create-home "$APP_USER"
usermod -aG www-data "$APP_USER"

# ── 3. Create bare Git repo on VPS ───────────────────────────
echo "[3] Creating bare git repo at $REPO_DIR..."
mkdir -p "$REPO_DIR"
git init --bare "$REPO_DIR"
chown -R "$APP_USER":"$APP_USER" "$REPO_DIR"

# ── 4. First checkout of app code ────────────────────────────
echo "[4] Checking out app for the first time..."
mkdir -p "$APP_DIR"
GIT_WORK_TREE="$APP_DIR" git --git-dir="$REPO_DIR" checkout -f main || true
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

# ── 5. Python virtualenv + dependencies ──────────────────────
echo "[5] Setting up Python virtualenv..."
su - "$APP_USER" -c "
    python3 -m venv $APP_DIR/venv
    $APP_DIR/venv/bin/pip install --quiet --upgrade pip
    $APP_DIR/venv/bin/pip install --quiet -r $APP_DIR/requirements.txt
"

# ── 6. Create .env file if it doesn't exist ──────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo "[6] Creating placeholder .env — FILL THIS IN before starting!"
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
    chmod 640 "$APP_DIR/.env"
fi

# ── 7. Collect static + migrate for first run ────────────────
echo "[7] Running initial migrate + collectstatic..."
su - "$APP_USER" -c "
    cd $APP_DIR
    $APP_DIR/venv/bin/python manage.py migrate --noinput
    $APP_DIR/venv/bin/python manage.py collectstatic --noinput --clear
"

# ── 8. Log directory ─────────────────────────────────────────
echo "[8] Creating log directory..."
mkdir -p "$LOG_DIR"
chown "$APP_USER":www-data "$LOG_DIR"
chmod 775 "$LOG_DIR"

# ── 9. Install post-receive hook ─────────────────────────────
echo "[9] Installing post-receive hook..."
cp "$APP_DIR/deploy/post-receive" "$REPO_DIR/hooks/post-receive"
chmod +x "$REPO_DIR/hooks/post-receive"
chown "$APP_USER":"$APP_USER" "$REPO_DIR/hooks/post-receive"

# Allow getmecare user to reload nginx + restart gunicorn without password
SUDOERS_LINE="$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/nginx, /bin/systemctl restart $GUNICORN_SERVICE, /bin/systemctl reload nginx, /bin/cp $APP_DIR/nginx/getmecare.conf /etc/nginx/sites-available/getmecare, /bin/ln -s *"
echo "$SUDOERS_LINE" > /etc/sudoers.d/getmecare-deploy
chmod 440 /etc/sudoers.d/getmecare-deploy

# ── 10. Gunicorn systemd service ─────────────────────────────
echo "[10] Installing Gunicorn service..."
# Replace placeholder domain in service file if needed
cp "$APP_DIR/deploy/gunicorn.service" \
   "/etc/systemd/system/$GUNICORN_SERVICE.service"
systemctl daemon-reload
systemctl enable "$GUNICORN_SERVICE"
systemctl start  "$GUNICORN_SERVICE"

# ── 11. Nginx site config ────────────────────────────────────
echo "[11] Installing Nginx config..."
# Replace YOUR_DOMAIN placeholder with the real domain
sed "s/YOUR_DOMAIN/$DOMAIN/g" "$APP_DIR/nginx/getmecare.conf" \
    > "/etc/nginx/sites-available/getmecare"
ln -sf /etc/nginx/sites-available/getmecare \
       /etc/nginx/sites-enabled/getmecare
# Remove default site if present
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 12. Firewall ─────────────────────────────────────────────
echo "[12] Configuring UFW firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# ── 13. SSL cert with Let's Encrypt ──────────────────────────
echo "[13] Obtaining SSL certificate for $DOMAIN..."
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos -m "admin@$DOMAIN" || \
    echo "  SSL cert failed — run certbot manually after DNS is pointed."

echo ""
echo "====================================================="
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Fill in /home/$APP_USER/app/.env with your real secrets"
echo "  2. Add the VPS as a git remote on your local machine:"
echo "     git remote add vps $APP_USER@YOUR_VPS_IP:$REPO_DIR"
echo "  3. Push to deploy:"
echo "     git push vps main"
echo "====================================================="
