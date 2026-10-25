# Sweet Spot deployment

These commands target the Vultr VPS at `144.202.27.51` (Ubuntu 24.04 or newer; **the live server runs Ubuntu 26.04 `resolute`**, which Docker's official repository supports). Run them as a user with `sudo` access; on the live server they were run as `root`, which also works (drop `sudo`).

## Current deployment (2026-10-25)

- URL: **https://sweetspotav.tech** (root `/` redirects to `/app/`). Let's Encrypt certificate issued by Caddy, valid to 2027-01-22, renewed automatically.
- Checkout: `/srv/sweetspot` (owned by root), stack: `deploy/docker-compose.yml` (`deploy-api-1`, `deploy-caddy-1`), Docker 29.9, Compose v5.6.
- `.env`: `/srv/sweetspot/.env` (mode 600) with `DOMAIN=sweetspotav.tech`, `SITE_ADDRESS="sweetspotav.tech, 144-202-27-51.sslip.io"` and `DATA_DIR=/data` set; the Gemini and SerpApi keys are configured.
- `deploy/smoke.sh https://sweetspotav.tech`: all checks PASS; the first `optimize` after a restart takes about 25 s, and repeats are instant.

## Rotating API keys

On the server (keys never go into the repo or chat):

```bash
cd /srv/sweetspot
nano .env        # set GEMINI_API_KEY=... and SERPAPI_KEY=...
docker compose -f deploy/docker-compose.yml up -d   # recreates the containers with the new env
bash deploy/smoke.sh https://sweetspotav.tech
```

## One-time setup

Install Docker Engine and the Compose plugin from Docker's official repository:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg ufw git openssl python3
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and back in now so your new `docker` group membership takes effect. Run the remaining commands as the same user.

Allow SSH and web traffic, and add a 2 GB swap file **only if `swapon --show` prints nothing** (the live server already has an 8 GB `/swapfile`, so this step was skipped there):

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Clone the repository and create the server-only environment file:

```bash
sudo install -d -o "$USER" -g "$USER" /srv/sweetspot
git clone https://github.com/autonomical1/sweetspot.git /srv/sweetspot
cp /srv/sweetspot/.env.example /srv/sweetspot/.env
chmod 600 /srv/sweetspot/.env
sed -i 's/^DOMAIN=.*/DOMAIN=sweetspotav.tech/' /srv/sweetspot/.env
sed -i 's/^SITE_ADDRESS=.*/SITE_ADDRESS="sweetspotav.tech, 144-202-27-51.sslip.io"/' /srv/sweetspot/.env
cd /srv/sweetspot
docker compose -f deploy/docker-compose.yml up -d --build
```

## Updates and rollback

```bash
cd /srv/sweetspot
git pull && docker compose -f deploy/docker-compose.yml up -d --build
```

To roll back to the known-good tag:

```bash
cd /srv/sweetspot
git fetch --tags
git checkout demo-ok
docker compose -f deploy/docker-compose.yml up -d --build
```

## Domain, logs, and data

Create a DNS A record for the new `.tech` hostname pointing to `144.202.27.51`, then update the environment and restart:

```bash
cd /srv/sweetspot
sed -i 's/^SITE_ADDRESS=.*/SITE_ADDRESS="yourname.tech, 144-202-27-51.sslip.io"/' .env
sed -i 's/^DOMAIN=.*/DOMAIN=yourname.tech/' .env
docker compose -f deploy/docker-compose.yml up -d
```

Useful operations:

```bash
docker compose -f deploy/docker-compose.yml logs -f api caddy
docker compose -f deploy/docker-compose.yml restart
docker compose -f deploy/docker-compose.yml ps
```

Room and photo data is stored in the named Docker volume `sweetspot_data` mounted at `/data` in the API container. Caddy certificates and configuration persist in `caddy_data` and `caddy_config`.

## Smoke test

From a machine with Bash, curl, Python 3 and OpenSSL (all present on the server after step 1):

```bash
cd /srv/sweetspot
bash deploy/smoke.sh https://sweetspotav.tech
```

## Web app build

The React/Vite app in `webapp/` is built in the Node stage of
`deploy/Dockerfile`. Its output is copied into `web/` in the final API image.
The Vite app is served at `/app/`;
the root redirect opens `/app/`.

Rebuild the production image locally or on the VPS with:

```bash
docker compose -f deploy/docker-compose.yml build api
docker compose -f deploy/docker-compose.yml up -d api caddy
```

Verify the generated app and its assets after it starts:

```bash
bash deploy/smoke.sh http://localhost
# Or, from a machine that can reach the deployment:
bash deploy/smoke.sh https://sweetspotav.tech
```

The smoke script checks that `/app/` has Vite's `#root` element, follows its
hashed JavaScript asset and verifies its JavaScript content type, and fetches
`/app/models/projector.glb`.

## Live domain (2026-10-25)

`https://sweetspotav.tech` is live: DNS `@ A 144.202.27.51` (registrar nameservers `tech-domains.venus.orderbox-dns.com`), `/srv/sweetspot/.env` has `DOMAIN=sweetspotav.tech` and `SITE_ADDRESS="sweetspotav.tech, 144-202-27-51.sslip.io"` (the sslip.io host stays as a fallback; the previous file is `.env.bak-pre-domain`). Caddy obtained the Let's Encrypt certificate itself; the first attempt failed because Let's Encrypt's secondary check still saw the old empty DNS answer, and Caddy's automatic retry about a minute later succeeded. Do not restart Caddy repeatedly while a certificate is pending (rate limits). The API keys (`GEMINI_API_KEY`, `SERPAPI_KEY`) and `GEMINI_MODEL=gemini-3.8-flash` are set in the server `.env`, so older notes above saying the keys are empty are out of date.
