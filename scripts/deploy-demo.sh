#!/bin/bash
# Deploy EarA demo (HTTP origin behind Cloudflare proxy).
set -euo pipefail

DOMAIN="eara.cloudhosting.pp.ua"
WEB_ROOT="/var/www/eara"
CONF="/etc/nginx/sites-available/${DOMAIN}"
ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"
SOURCE="${1:-$HOME/eara-demo}"

echo "→ Web root: $WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo rsync -a --delete "$SOURCE/" "$WEB_ROOT/"
sudo chown -R www-data:www-data "$WEB_ROOT"

sudo tee "$CONF" > /dev/null <<EOF
server {
    listen 192.168.1.8:80;
    listen 176.122.105.19:80;
    listen 127.0.0.1:80;
    server_name ${DOMAIN};

    root ${WEB_ROOT};
    index index.html;

    add_header X-Content-Type-Options nosniff always;

    location / {
        try_files \$uri \$uri/ =404;
    }
}
EOF

sudo ln -sf "$CONF" "$ENABLED"
sudo nginx -t
sudo systemctl reload nginx

# Cloudflare tunnel ingress (if /etc/cloudflared/config.yml exists)
if [ -f /etc/cloudflared/config.yml ] && ! grep -q "hostname: ${DOMAIN}" /etc/cloudflared/config.yml; then
  echo "→ Add ${DOMAIN} to /etc/cloudflared/config.yml ingress manually"
fi

echo "Done (HTTP): configure Cloudflare SSL = Full or DNS-only for certbot"
echo "Public test: curl -H 'Host: ${DOMAIN}' http://192.168.1.8/"
