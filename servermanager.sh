#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  AX-Manager — installer & control panel for ServerManager
#  Manage your servers over SSH from Telegram.   by AtronixX-Core
#
#  Usage:  AX-Manager [command]
#    (no command)        interactive control panel
#    install             guided installation (or re-configure)
#    status              dashboard
#    doctor              run health checks and explain problems
#    start | stop | restart
#    logs [-f]           show (or follow) the bot's log
#    update              update to the latest version (backs up first)
#    settings            change token / admin / name / timezone / networks
#    host-access [enable|disable|status|test]
#                        let the admin manage THIS server from Telegram
#    backup              local backup of data + settings (tar.gz)
#    import-data <dir>   import settings + data from another install directory
#    uninstall           remove the bot (asks before deleting data)
#    version | help
#
#  Non-interactive install: SM_YES=1 SM_BOT_TOKEN=… SM_ADMIN_ID=… AX-Manager install
# ──────────────────────────────────────────────────────────────────────────────
set -uo pipefail

SM_VERSION="1.0.0"
SM_REPO="${SM_REPO:-AtronixX-Core/AtronixX-ServerManager}"   # override to install from a fork
SM_BRANCH="${SM_BRANCH:-main}"
SM_DIR="${SM_DIR:-/opt/servermanager}"
CONTAINER="servermanager"
NETWORK="servermanager_net"
BIN_PATH="${SM_BIN:-/usr/local/bin/AX-Manager}"
ALIAS_PATH="$(dirname "$BIN_PATH")/servermanager"   # kept as an alias of AX-Manager
DEFAULT_SUBNETS=("172.28.77.0/24" "172.29.77.0/24" "172.30.77.0/24" "10.222.77.0/24" "192.168.222.0/24")

ENV_FILE="$SM_DIR/.env"
COMPOSE_FILE="$SM_DIR/docker-compose.yml"
DATA_DIR="$SM_DIR/data"
SRC_DIR="$SM_DIR/src"
CONF_FILE="$SM_DIR/.install.conf"
BACKUP_DIR="$SM_DIR/backups"
LOG_TMP="$(mktemp -t servermanager.XXXXXX)"
cleanup() { rm -f "$LOG_TMP"; [ -t 1 ] && tput cnorm 2>/dev/null; return 0; }
trap cleanup EXIT
trap 'echo; exit 130' INT

# ── terminal styling ─────────────────────────────────────────────────────────
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  RST=$'\033[0m'; BOLD=$'\033[1m'; DIM=$'\033[38;5;242m'
  RED=$'\033[38;5;196m'; GRN=$'\033[38;5;82m'; YEL=$'\033[38;5;214m'
  BLU=$'\033[38;5;75m'; CYN=$'\033[38;5;51m'; GRY=$'\033[38;5;242m'; TXT=$'\033[38;5;255m'
  INTERACTIVE_UI=1
else
  RST=""; BOLD=""; DIM=""; RED=""; GRN=""; YEL=""; BLU=""; CYN=""; GRY=""; TXT=""
  INTERACTIVE_UI=0
fi
MAG="$RED"   # accent colour
FRAMES=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")

# terminal width, capped so lines stay readable on wide screens
cols() { local c; c="$(tput cols 2>/dev/null || echo 78)"; [ "$c" -gt 78 ] && c=78; [ "$c" -lt 40 ] && c=40; echo "$c"; }
repeat() { local n="$1" ch="$2" out=""; while [ "$n" -gt 0 ]; do out+="$ch"; n=$((n - 1)); done; printf '%s' "$out"; }
vlen() { printf '%s' "$1" | sed 's/\x1b\[[0-9;]*m//g' | LC_ALL=C.UTF-8 wc -m; }

ok()   { printf '  %s✔%s %s\n' "$GRN" "$RST" "$*"; }
info() { printf '  %sℹ%s %s\n' "$BLU" "$RST" "$*"; }
warn() { printf '  %s⚠%s %s\n' "$YEL" "$RST" "$*"; }
bad()  { printf '  %s✘%s %s\n' "$RED" "$RST" "$*"; }
die()  { printf '\n  %s✘ %s%s\n\n' "$RED" "$*" "$RST" >&2; exit 1; }
rule() { printf '%s%s%s\n' "$GRY" "$(repeat "$(cols)" '─')" "$RST"; }
title() { printf '\n %s%s%s\n' "$BOLD" "$*" "$RST"; rule; }

# step N TOTAL "Title"  →  ▰▰▱▱▱▱  Title · step 2 of 6
step() {
  local n="$1" t="$2" bar="" i
  for ((i = 1; i <= t; i++)); do if [ "$i" -le "$n" ]; then bar+="▰"; else bar+="▱"; fi; done
  printf '\n %s%s%s  %s%s%s %s· step %s of %s%s\n' "$RED" "$bar" "$RST" "$BOLD$TXT" "$3" "$RST" "$GRY" "$n" "$t" "$RST"
}

banner() {
  [ "$INTERACTIVE_UI" = 1 ] && [ "${NO_CLEAR:-0}" != 1 ] && clear
  printf '\n'
  if [ "$(cols)" -ge 66 ]; then
    printf '%s' "$RED"
    cat <<'ART'
 █████╗ ████████╗██████╗  ██████╗ ███╗   ██╗██╗██╗  ██╗██╗  ██╗
██╔══██╗╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║██║╚██╗██╔╝╚██╗██╔╝
███████║   ██║   ██████╔╝██║   ██║██╔██╗ ██║██║ ╚███╔╝  ╚███╔╝
██╔══██║   ██║   ██╔══██╗██║   ██║██║╚██╗██║██║ ██╔██╗  ██╔██╗
██║  ██║   ██║   ██║  ██║╚██████╔╝██║ ╚████║██║██╔╝ ██╗██╔╝ ██╗
╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
ART
    printf '%s' "$RST"
  else
    printf ' %s%s▞▚ ATRONIXX ▞▚%s\n' "$RED" "$BOLD" "$RST"
  fi
  printf ' %s%sSERVER MANAGER%s  %sv%s%s   %sCLI: AX-Manager%s\n' "$BOLD" "$TXT" "$RST" "$GRY" "$SM_VERSION" "$RST" "$GRY" "$RST"
  rule
  printf ' %s📡 Channel: %s@AtronixX_Core%s   %s💬 Support: %s@AtronixX_Support%s\n' "$TXT" "$RED" "$RST" "$TXT" "$RED" "$RST"
  rule
}

# box helpers (keep emoji out of boxed rows: they break the padding)
box_top() { printf ' %s╭%s╮%s\n' "$GRY" "$(repeat $(($(cols) - 4)) '─')" "$RST"; }
box_mid() { printf ' %s├%s┤%s\n' "$GRY" "$(repeat $(($(cols) - 4)) '─')" "$RST"; }
box_bot() { printf ' %s╰%s╯%s\n' "$GRY" "$(repeat $(($(cols) - 4)) '─')" "$RST"; }
box_row() {
  local text="$1" width pad
  width=$(($(cols) - 6)); pad=$((width - $(vlen "$text")))
  [ "$pad" -lt 0 ] && pad=0
  printf ' %s│%s %s%*s %s│%s\n' "$GRY" "$RST" "$text" "$pad" "" "$GRY" "$RST"
}

# Run a command with a spinner; show the tail of its output when it fails.
spin() {
  local msg="$1"; shift
  : >"$LOG_TMP"
  ( "$@" ) >"$LOG_TMP" 2>&1 &
  local pid=$! i=0 start=$SECONDS rc
  if [ "$INTERACTIVE_UI" = 1 ]; then
    tput civis 2>/dev/null || true
    while kill -0 "$pid" 2>/dev/null; do
      printf '\r  %s%s%s %s %s(%ss)%s\033[K' "$CYN" "${FRAMES[i % ${#FRAMES[@]}]}" "$RST" "$msg" "$DIM" "$((SECONDS - start))" "$RST"
      i=$((i + 1)); sleep 0.1
    done
    tput cnorm 2>/dev/null || true
    printf '\r\033[K'
  fi
  wait "$pid"; rc=$?
  if [ "$rc" -eq 0 ]; then
    ok "$msg"
  else
    bad "$msg"
    sed 's/^/      /' "$LOG_TMP" | tail -n 15 >&2
  fi
  return "$rc"
}

# ── prompts (read from the terminal even when the script itself is piped) ────
is_yes_mode() { [ "${SM_YES:-0}" = 1 ]; }
can_prompt() { ! is_yes_mode && [ -r /dev/tty ] && [ -w /dev/tty ]; }

# ask "Question" "default" → echoes the answer
ask() {
  local q="$1" def="${2:-}" ans=""
  if can_prompt; then
    printf '  %s?%s %s %s%s%s ' "$MAG" "$RST" "$q" "$DIM" "${def:+[$def]}" "$RST" >/dev/tty
    IFS= read -r ans </dev/tty || ans=""
  fi
  printf '%s' "${ans:-$def}"
}

ask_secret() {
  local q="$1" ans=""
  if can_prompt; then
    printf '  %s?%s %s ' "$MAG" "$RST" "$q" >/dev/tty
    IFS= read -rs ans </dev/tty || ans=""
    printf '\n' >/dev/tty
  fi
  printf '%s' "$ans"
}

# confirm "Question" y|n → 0 for yes
confirm() {
  local q="$1" def="${2:-y}" ans hint="[Y/n]"
  [ "$def" = n ] && hint="[y/N]"
  if ! can_prompt; then [ "$def" = y ]; return; fi
  printf '  %s?%s %s %s%s%s ' "$MAG" "$RST" "$q" "$DIM" "$hint" "$RST" >/dev/tty
  IFS= read -r ans </dev/tty || ans=""
  ans="${ans:-$def}"
  [[ "$ans" =~ ^[Yy] ]]
}

# ── small helpers ────────────────────────────────────────────────────────────
need_root() { [ "$(id -u)" -eq 0 ] || die "Please run as root:  sudo AX-Manager ${1:-}"; }
have() { command -v "$1" >/dev/null 2>&1; }
is_installed() { [ -f "$ENV_FILE" ] && [ -f "$COMPOSE_FILE" ]; }
need_installed() { is_installed || die "ServerManager is not installed yet. Run:  sudo AX-Manager install"; }
dc() { docker compose -f "$COMPOSE_FILE" --project-directory "$SM_DIR" "$@"; }
container_state() { docker inspect -f '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo "absent"; }

env_get() { [ -f "$ENV_FILE" ] && grep -m1 "^$1=" "$ENV_FILE" | cut -d= -f2- || true; }
env_set() {
  local key="$1" val="$2" tmp
  tmp="$(mktemp)"
  awk -v k="$key" -v v="$val" 'BEGIN{d=0} index($0,k"=")==1{print k"="v; d=1; next} {print} END{if(!d)print k"="v}' "$ENV_FILE" >"$tmp"
  cat "$tmp" >"$ENV_FILE"; rm -f "$tmp"; chmod 600 "$ENV_FILE"
}
conf_get() { [ -f "$CONF_FILE" ] && grep -m1 "^$1=" "$CONF_FILE" | cut -d= -f2- || true; }
conf_set() {
  mkdir -p "$SM_DIR"; touch "$CONF_FILE"
  grep -v "^$1=" "$CONF_FILE" >"$CONF_FILE.tmp" || true
  printf '%s=%s\n' "$1" "$2" >>"$CONF_FILE.tmp"; mv "$CONF_FILE.tmp" "$CONF_FILE"
}

random_pass() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24; }
detect_tz() {
  local tz=""
  have timedatectl && tz="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
  [ -z "$tz" ] && [ -r /etc/timezone ] && tz="$(head -n1 /etc/timezone)"
  printf '%s' "${tz:-UTC}"
}
public_ips() { hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | grep -Ev '^(10\.|127\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|169\.254\.|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.)' | paste -sd, - || true; }
first_ip() { public_ips | cut -d, -f1; }
clean_brand() { printf '%s' "$1" | tr -cd 'A-Za-z0-9 ._-' | cut -c1-40; }
current_image() { dc config --images 2>/dev/null | head -n1; }
default_image() { local r="${SM_REPO,,}"; printf 'ghcr.io/%s:latest' "$r"; }
container_uid() { docker run --rm --entrypoint id "$(current_image)" -u 2>/dev/null || echo 999; }

fix_permissions() {
  local uid; uid="$(container_uid)"
  mkdir -p "$DATA_DIR"
  chown -R "$uid:$uid" "$DATA_DIR" 2>/dev/null || true
  chmod 700 "$DATA_DIR"; chmod 600 "$ENV_FILE" 2>/dev/null || true
}

telegram_getme() {
  # prints the bot username on success
  curl -fsS --max-time 10 "https://api.telegram.org/bot$1/getMe" 2>/dev/null | grep -o '"username":"[^"]*"' | head -n1 | cut -d'"' -f4
}

# ── pre-flight ───────────────────────────────────────────────────────────────
preflight() {
  need_root "install"
  [ "$(uname -s)" = Linux ] || die "Linux is required."
  have curl || { have apt-get && spin "Installing curl" apt-get install -y curl; } || die "curl is required."
  local arch; arch="$(uname -m)"
  case "$arch" in x86_64|aarch64|arm64) ok "Architecture: $arch" ;; *) warn "Untested architecture: $arch" ;; esac
  local free_mb; free_mb="$(df -Pm / | awk 'NR==2{print $4}')"
  [ "${free_mb:-0}" -lt 800 ] && warn "Only ${free_mb} MB free on / — at least 800 MB is recommended."
  local mem_mb; mem_mb="$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)"
  [ "${mem_mb:-0}" -lt 400 ] && warn "Low memory (${mem_mb} MB). The bot itself needs about 100–200 MB."
  ok "System looks good (${mem_mb:-?} MB RAM, ${free_mb:-?} MB free)"
}

install_docker() {
  if have docker && docker info >/dev/null 2>&1; then
    ok "Docker is ready ($(docker --version | awk '{print $3}' | tr -d ','))"
  else
    spin "Installing Docker (official script)" sh -c 'curl -fsSL https://get.docker.com | sh' || die "Docker installation failed."
    systemctl enable --now docker >/dev/null 2>&1 || true
    docker info >/dev/null 2>&1 || die "Docker is installed but not running."
  fi
  if ! docker compose version >/dev/null 2>&1; then
    have apt-get && spin "Installing the Docker Compose plugin" apt-get install -y docker-compose-plugin
    docker compose version >/dev/null 2>&1 || die "The Docker Compose plugin (v2) is required."
  fi
  ok "Docker Compose ready"
}

# ── subnet for the bot's private network ─────────────────────────────────────
subnet_in_use() {
  local cidr="$1" result
  have python3 || return 1
  # The verdict is printed (not the exit status) so a missing `ip`/`docker` can't flip it under pipefail.
  result="$({
    ip -o route 2>/dev/null | awk '{print $1}'
    docker network ls -q 2>/dev/null | xargs -r docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}}{{"\n"}}{{end}}' 2>/dev/null
  } | python3 -c '
import ipaddress, sys
want = ipaddress.ip_network(sys.argv[1])
for line in sys.stdin:
    try:
        net = ipaddress.ip_network(line.strip(), strict=False)
    except ValueError:
        continue
    if net.version == 4 and net.prefixlen > 0 and net.overlaps(want):
        print(1)
        break
' "$cidr" 2>/dev/null || true)"
  [ "$result" = 1 ]
}

pick_subnet() {
  local current c; current="$(env_get SM_SUBNET)"
  if [ -n "$current" ]; then printf '%s' "$current"; return; fi
  for c in "${DEFAULT_SUBNETS[@]}"; do
    subnet_in_use "$c" || { printf '%s' "$c"; return; }
  done
  printf '%s' "${DEFAULT_SUBNETS[0]}"
}

# Docker bridges default to MTU 1500 even when the server's uplink is smaller (common on VPS / tunnels), which
# makes SSH key exchange stall on large packets. Match the bridge to the real uplink.
detect_mtu() {
  local dev mtu
  dev="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="dev"){print $(i+1); exit}}')"
  mtu="$(cat "/sys/class/net/${dev:-none}/mtu" 2>/dev/null || true)"
  if [[ "$mtu" =~ ^[0-9]+$ ]] && [ "$mtu" -ge 1280 ] && [ "$mtu" -le 1500 ]; then printf '%s' "$mtu"; else printf '1500'; fi
}
ensure_mtu() { [ -n "$(env_get SM_MTU)" ] || env_set SM_MTU "$(detect_mtu)"; }

# ── compose file ─────────────────────────────────────────────────────────────
write_compose() {
  local mode="$1" image_block
  if [ "$mode" = build ]; then
    image_block="    image: servermanager:local
    build: ./src"
  else
    image_block="    image: \${SM_IMAGE:-$(default_image)}"
  fi
  cat >"$COMPOSE_FILE" <<EOF
# Generated by the servermanager installer. Safe to edit; it is kept as it is.
name: servermanager

services:
  bot:
${image_block}
    container_name: ${CONTAINER}
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/data
    networks: [sm_net]
    extra_hosts:
      - "host.docker.internal:host-gateway"
    mem_limit: 220m
    memswap_limit: 220m
    cpus: "0.5"
    pids_limit: 128
    security_opt: ["no-new-privileges:true"]
    read_only: true
    tmpfs:
      - /tmp
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

networks:
  sm_net:
    name: ${NETWORK}
    driver: bridge
    driver_opts:
      com.docker.network.driver.mtu: "\${SM_MTU:-1500}"
    ipam:
      config:
        - subnet: \${SM_SUBNET:-172.28.77.0/24}
EOF
}

# ── getting the application (image first, source as a fallback) ──────────────
local_source_dir() {
  local here; here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || return 1
  if [ -f "$here/Dockerfile" ] && [ -f "$here/main.py" ]; then printf '%s' "$here"; else return 1; fi
}

fetch_source() {
  local local_dir
  rm -rf "$SRC_DIR"; mkdir -p "$SRC_DIR"
  if local_dir="$(local_source_dir)" && [ "$local_dir" != "$SRC_DIR" ]; then
    tar -C "$local_dir" --exclude=.git --exclude=data --exclude=__pycache__ --exclude=.pytest_cache -cf - . | tar -C "$SRC_DIR" -xf -
  else
    curl -fsSL "https://codeload.github.com/${SM_REPO}/tar.gz/refs/heads/${SM_BRANCH}" | tar -xz --strip-components=1 -C "$SRC_DIR"
  fi
}

obtain_app() {
  local mode="${1:-auto}"
  if [ "$mode" = auto ]; then
    write_compose image
    if spin "Downloading the ready-made image" dc pull; then conf_set MODE image; return 0; fi
    warn "No prebuilt image available — building from source instead (takes a minute or two)."
    mode=build
  fi
  if [ "$mode" = image ]; then
    write_compose image
    spin "Downloading the ready-made image" dc pull || die "Could not pull the image."
    conf_set MODE image; return 0
  fi
  spin "Fetching the source code" fetch_source || die "Could not get the source code."
  write_compose build
  spin "Building the image" dc build || die "Image build failed."
  conf_set MODE build
}

wait_started() {
  local i=0
  while [ "$i" -lt 45 ]; do
    if docker logs "$CONTAINER" 2>&1 | grep -q "started as @"; then return 0; fi
    case "$(container_state)" in exited|dead|absent) return 1 ;; esac
    sleep 2; i=$((i + 1))
  done
  return 1
}

start_and_verify() {
  spin "Starting the bot" dc up -d --remove-orphans || die "Could not start the container."
  if spin "Waiting for the bot to come online" wait_started; then
    return 0
  fi
  bad "The bot did not start correctly. Last log lines:"
  docker logs --tail 15 "$CONTAINER" 2>&1 | sed 's/^/      /' >&2
  return 1
}

# ── install ──────────────────────────────────────────────────────────────────
cmd_install() {
  need_root install
  banner
  local total=6 token admin pass brand support tz bot_name="" blocked subnet ans
  local reinstall=0; is_installed && reinstall=1

  printf ' %sWhat happens next%s\n' "$BOLD$TXT" "$RST"
  printf '  %s▸%s check your system   %s▸%s Docker   %s▸%s a few questions\n' "$RED" "$RST" "$RED" "$RST" "$RED" "$RST"
  printf '  %s▸%s get the app         %s▸%s start    %s▸%s optional: manage this server\n' "$RED" "$RST" "$RED" "$RST" "$RED" "$RST"

  step 1 $total "Checking your system"
  preflight

  step 2 $total "Docker"
  install_docker

  step 3 $total "A few questions"
  mkdir -p "$SM_DIR" "$DATA_DIR"
  [ -f "$ENV_FILE" ] || : >"$ENV_FILE"
  chmod 600 "$ENV_FILE"

  if [ "$reinstall" = 1 ]; then
    info "Existing settings found — press Enter to keep each value."
  else
    printf '\n  %sCreate a bot with @BotFather in Telegram and copy its token.%s\n' "$DIM" "$RST"
  fi

  while :; do
    token="$(env_get BOT_TOKEN)"; token="${SM_BOT_TOKEN:-$token}"
    if [ -z "${SM_BOT_TOKEN:-}" ]; then
      local shown=""; [ -n "$token" ] && shown="${token%%:*}:••••"
      ans="$(ask "🤖 Bot token" "$shown")"
      [ -n "$ans" ] && [ "$ans" != "$shown" ] && token="$ans"
    fi
    if [[ "$token" =~ ^[0-9]{6,}:[A-Za-z0-9_-]{30,}$ ]]; then
      if bot_name="$(telegram_getme "$token")" && [ -n "$bot_name" ]; then ok "Token is valid — your bot is @$bot_name"
      else warn "Could not verify the token with Telegram right now (network?). Continuing."; fi
      break
    fi
    is_yes_mode && die "SM_BOT_TOKEN is missing or invalid."
    can_prompt || die "A valid bot token is required (set SM_BOT_TOKEN)."
    bad "That doesn't look like a bot token (it looks like 123456789:AA…)."
  done

  while :; do
    admin="$(env_get ADMIN_ID)"; admin="${SM_ADMIN_ID:-$admin}"
    if [ -z "${SM_ADMIN_ID:-}" ]; then admin="$(ask "🆔 Your numeric Telegram ID (@userinfobot shows it)" "$admin")"; fi
    [[ "$admin" =~ ^[0-9]{5,}$ ]] && break
    is_yes_mode && die "SM_ADMIN_ID is missing or invalid."
    can_prompt || die "A numeric admin ID is required (set SM_ADMIN_ID)."
    bad "The ID must be a number, e.g. 123456789."
  done

  brand="$(clean_brand "${SM_BRAND:-$(ask "🏷  Name shown in the bot" "$(env_get BOT_NAME)")}")"
  support="${SM_SUPPORT:-$(ask "💬 Support username for your users (optional)" "$(env_get SUPPORT_USERNAME)")}"
  [[ -z "$support" || "$support" =~ ^@?[A-Za-z][A-Za-z0-9_]{4,31}$ ]] || { warn "Ignoring invalid support username."; support=""; }
  tz="$(env_get TZ)"; tz="${tz:-$(detect_tz)}"

  pass="$(env_get BACKUP_PASSPHRASE)"; pass="${SM_BACKUP_PASS:-$pass}"
  local generated_pass=0
  if [ -z "$pass" ]; then pass="$(random_pass)"; generated_pass=1; fi
  [[ "$pass" =~ ^[A-Za-z0-9._@%+=,:-]{8,}$ ]] || die "Backup password must be 8+ characters from: letters, digits and . _ @ % + = , : -"

  blocked="$(env_get BLOCKED_IPS)"; [ -z "$blocked" ] && blocked="$(public_ips)"
  subnet="$(pick_subnet)"

  env_set BOT_TOKEN "$token"; env_set ADMIN_ID "$admin"; env_set BACKUP_PASSPHRASE "$pass"
  env_set BOT_NAME "${brand:-ServerManager}"; env_set SUPPORT_USERNAME "$support"; env_set TZ "$tz"
  env_set BLOCKED_IPS "$blocked"; env_set SM_SUBNET "$subnet"; ensure_mtu
  local kv
  for kv in BACKUP_INTERVAL_HOURS=24 MAX_LIVE_SESSIONS=20 IDLE_TIMEOUT_MIN=10 MAX_SESSION_HOURS=2 WATCH_INTERVAL_MIN=5 MAX_WATCH_PER_USER=10 \
            ALLOWED_NETS= HOST_ACCESS=0 HOST_SSH_ADDR=host.docker.internal HOST_SSH_PORT=22 HOST_SSH_USER=root HOST_SSH_FINGERPRINT=; do
    grep -q "^${kv%%=*}=" "$ENV_FILE" || env_set "${kv%%=*}" "${kv#*=}"
  done
  ok "Settings saved to $ENV_FILE (private, mode 600)"

  step 4 $total "Getting the application"
  [ "$reinstall" = 1 ] && dc down >/dev/null 2>&1
  local mode; mode="$(conf_get MODE)"
  obtain_app "${mode:-auto}"
  fix_permissions

  step 5 $total "Starting"
  local started=1
  start_and_verify || started=0
  install_self

  step 6 $total "Optional: manage THIS server from Telegram"
  if [ "$started" = 1 ]; then
    if [ "${SM_HOST_ACCESS:-}" = 1 ]; then
      host_access_enable || warn "Host access was not enabled. Retry with:  AX-Manager host-access enable"
    elif [ "$(env_get HOST_ACCESS)" != 1 ] && can_prompt; then
      printf '  %sThis lets you (the admin only) open a terminal, browse files and run tools on the machine the bot runs on.%s\n' "$DIM" "$RST"
      printf '  %sIt gives full control of this server to your Telegram account, so protect that account with 2-step verification.%s\n' "$DIM" "$RST"
      if confirm "Enable \"This server\" access?" n; then
        host_access_enable || warn "Host access was not enabled. Retry with:  AX-Manager host-access enable"
      else
        info "Skipped. Enable it any time with:  AX-Manager host-access enable"
      fi
    else
      info "Host access: $([ "$(env_get HOST_ACCESS)" = 1 ] && echo enabled || echo off)"
    fi
  else
    warn "Skipping — fix the problem above first."
  fi

  summary "$started" "$generated_pass" "$pass" "$bot_name"
}

summary() {
  local started="$1" generated="$2" pass="$3" bot_name="$4"
  printf '\n'
  box_top
  if [ "$started" = 1 ]; then
    box_row "${BOLD}${GRN}SERVER MANAGER IS RUNNING${RST}"
  else
    box_row "${BOLD}${RED}INSTALLED, BUT THE BOT IS NOT RUNNING${RST}"
  fi
  box_mid
  if [ "$started" = 1 ]; then
    [ -n "$bot_name" ] && box_row "${GRY}Your bot  ${RST}${CYN}https://t.me/${bot_name}${RST}"
    box_row "${GRY}Next      ${RST}open the bot and send ${BOLD}/start${RST}"
  else
    box_row "${GRY}Fix it    ${RST}run ${BOLD}AX-Manager doctor${RST}"
  fi
  box_row "${GRY}Panel     ${RST}${BOLD}sudo AX-Manager${RST}"
  box_row "${GRY}Commands  ${RST}status · logs -f · update · doctor"
  box_row "${GRY}Folder    ${RST}${SM_DIR}"
  if [ "$generated" = 1 ]; then
    box_mid
    box_row "${YEL}${BOLD}BACKUP PASSWORD${RST}${YEL} - save it, you need it to restore${RST}"
    box_row "${BOLD}${pass}${RST}"
  fi
  box_bot
  printf ' %s📡 @AtronixX_Core   💬 @AtronixX_Support%s\n\n' "$GRY" "$RST"
}

install_self() {
  local src="${BASH_SOURCE[0]}"
  if [ -r "$src" ] && [ "$(readlink -f "$src")" != "$(readlink -f "$BIN_PATH" 2>/dev/null)" ]; then
    install -m 755 "$src" "$BIN_PATH" 2>/dev/null
  elif [ ! -x "$BIN_PATH" ]; then
    curl -fsSL "https://raw.githubusercontent.com/${SM_REPO}/${SM_BRANCH}/scripts/servermanager.sh" -o "$BIN_PATH" 2>/dev/null && chmod 755 "$BIN_PATH"
  fi
  [ -x "$BIN_PATH" ] && ln -sf "$BIN_PATH" "$ALIAS_PATH" 2>/dev/null
  return 0
}

# ── "This server" access ─────────────────────────────────────────────────────
ssh_port() { have sshd && sshd -T 2>/dev/null | awk '$1=="port"{print $2; exit}' || true; }
host_key_fingerprints() {
  local f out=""
  for f in /etc/ssh/ssh_host_*_key.pub; do
    [ -r "$f" ] || continue
    out+="$(ssh-keygen -lf "$f" 2>/dev/null | awk '{print $2}'),"
  done
  printf '%s' "${out%,}"
}
sshd_active() { systemctl is-active --quiet ssh 2>/dev/null || systemctl is-active --quiet sshd 2>/dev/null; }
user_home() { getent passwd "$1" | cut -d: -f6; }

remove_authorized_line() {
  local user="$1" home ak tmp
  home="$(user_home "$user")"; ak="$home/.ssh/authorized_keys"
  [ -f "$ak" ] || return 0
  tmp="$(mktemp)"; grep -vF "servermanager-bot" "$ak" >"$tmp" || true
  cat "$tmp" >"$ak"; rm -f "$tmp"
}

host_access_enable() {
  need_root host-access; need_installed
  title "Enable \"This server\" access"
  local user port subnet key="$DATA_DIR/host_key" home ak pins perm

  have ssh-keygen || { have apt-get && spin "Installing the OpenSSH client" apt-get install -y openssh-client; }
  if ! have sshd; then
    warn "The OpenSSH server is not installed (the bot connects to this machine over SSH)."
    confirm "Install openssh-server now?" y || return 1
    have apt-get || { bad "Please install openssh-server manually, then retry."; return 1; }
    spin "Installing openssh-server" apt-get install -y openssh-server || return 1
  fi
  if ! sshd_active; then
    spin "Starting the SSH service" sh -c 'systemctl enable --now ssh 2>/dev/null || systemctl enable --now sshd' || { bad "The SSH service is not running."; return 1; }
  fi
  port="$(ssh_port)"; port="${port:-22}"
  ok "SSH server is running on port $port"

  user="$(env_get HOST_SSH_USER)"; user="${SM_HOST_USER:-${user:-root}}"
  can_prompt && user="$(ask "Log in to this server as which user?" "$user")"
  id "$user" >/dev/null 2>&1 || { bad "User '$user' does not exist."; return 1; }
  perm="$(sshd -T -C "user=$user,host=localhost,addr=127.0.0.1" 2>/dev/null | awk '$1=="permitrootlogin"{print $2}')"
  if [ "$user" = root ] && [ "$perm" = no ]; then
    bad "sshd forbids root login (PermitRootLogin no). Choose another user, or set PermitRootLogin prohibit-password."
    return 1
  fi
  [ "$user" = root ] || info "Logging in as '$user' — tools like reboot use sudo if it is passwordless."

  subnet="$(env_get SM_SUBNET)"; [ -n "$subnet" ] || { bad "SM_SUBNET is missing in $ENV_FILE."; return 1; }

  if [ ! -f "$key" ]; then
    ssh-keygen -q -t ed25519 -N "" -C "servermanager-bot" -f "$key" || return 1
    ok "Created a dedicated key for the bot"
  else
    ok "Using the existing bot key"
  fi
  chmod 600 "$key"; chmod 644 "$key.pub"

  home="$(user_home "$user")"; ak="$home/.ssh/authorized_keys"
  install -d -m 700 -o "$user" "$home/.ssh" 2>/dev/null || mkdir -p "$home/.ssh"
  touch "$ak"; remove_authorized_line "$user"
  printf 'from="%s",restrict,pty %s\n' "$subnet" "$(cat "$key.pub")" >>"$ak"
  chown "$user" "$ak" 2>/dev/null || true; chmod 600 "$ak"
  ok "Authorized the key for '$user' — usable only from the bot's private network ($subnet)"

  if have ufw && ufw status 2>/dev/null | grep -q "Status: active"; then
    if ufw allow from "$subnet" to any port "$port" proto tcp comment "servermanager" >/dev/null 2>&1; then
      ok "Firewall (ufw): allowed $subnet → port $port"
    else
      warn "Could not add a ufw rule; allow $subnet to reach port $port yourself."
    fi
  fi
  if sshd -T 2>/dev/null | awk '$1=="listenaddress"{print $2}' | grep -qvE '^(0\.0\.0\.0|\[::\]|::)(:[0-9]+)?$'; then
    warn "sshd listens only on specific addresses. The bot reaches this machine through the Docker bridge; make sure sshd also listens there."
  fi

  pins="$(host_key_fingerprints)"
  env_set HOST_ACCESS 1; env_set HOST_SSH_PORT "$port"; env_set HOST_SSH_USER "$user"; env_set HOST_SSH_FINGERPRINT "$pins"
  ok "Pinned this server's SSH host keys (protects against impersonation)"

  fix_permissions
  spin "Restarting the bot" dc up -d --force-recreate || return 1
  wait_started || { bad "The bot did not come back up."; return 1; }
  host_access_test || { warn "The connection test failed — see above. Run  AX-Manager host-access test  after fixing it."; return 1; }
  printf '\n  %s✔ Done.%s In Telegram open the bot → %s🏠 This server%s.\n' "$GRN" "$RST" "$BOLD" "$RST"
  warn "Anyone controlling your Telegram admin account controls this server — enable 2-step verification."
}

host_access_disable() {
  need_root host-access; need_installed
  title "Disable \"This server\" access"
  local user subnet port; user="$(env_get HOST_SSH_USER)"; user="${user:-root}"
  subnet="$(env_get SM_SUBNET)"; port="$(env_get HOST_SSH_PORT)"
  id "$user" >/dev/null 2>&1 && remove_authorized_line "$user" && ok "Removed the bot's key from $user's authorized_keys"
  have ufw && ufw delete allow from "$subnet" to any port "${port:-22}" proto tcp >/dev/null 2>&1 && ok "Removed the firewall rule"
  rm -f "$DATA_DIR/host_key" "$DATA_DIR/host_key.pub"
  env_set HOST_ACCESS 0; env_set HOST_SSH_FINGERPRINT ""
  spin "Restarting the bot" dc up -d --force-recreate || return 1
  ok "\"This server\" access is off"
}

host_access_test() {
  [ "$(container_state)" = running ] || { bad "The bot is not running."; return 1; }
  printf '\n'
  docker exec "$CONTAINER" python3 scripts/hostcheck.py
}

host_access_status() {
  need_installed
  if [ "$(env_get HOST_ACCESS)" = 1 ]; then
    ok "Enabled — user $(env_get HOST_SSH_USER), port $(env_get HOST_SSH_PORT)"
    [ -f "$DATA_DIR/host_key" ] && info "Key: $DATA_DIR/host_key (created $(date -r "$DATA_DIR/host_key" '+%Y-%m-%d'))"
  else
    info "Off. Enable it with:  AX-Manager host-access enable"
  fi
}

cmd_host_access() {
  case "${1:-status}" in
    enable)  host_access_enable ;;
    disable) host_access_disable ;;
    test)    need_installed; host_access_test ;;
    status)  host_access_status ;;
    *) die "Usage: AX-Manager host-access [enable|disable|status|test]" ;;
  esac
}

# ── status dashboard ─────────────────────────────────────────────────────────
counters() { docker exec "$CONTAINER" python3 scripts/stats.py 2>/dev/null || true; }
fmt_uptime() {
  local started s d h m
  started="$(docker inspect -f '{{.State.StartedAt}}' "$CONTAINER" 2>/dev/null)" || return 0
  s=$(( $(date +%s) - $(date -d "$started" +%s 2>/dev/null || date +%s) ))
  d=$((s / 86400)); h=$((s % 86400 / 3600)); m=$((s % 3600 / 60))
  if [ "$d" -gt 0 ]; then printf '%sd %sh' "$d" "$h"; elif [ "$h" -gt 0 ]; then printf '%sh %sm' "$h" "$m"; else printf '%sm' "$m"; fi
}

dashboard() {
  local state sc label ram stats mode="-" users="-" subs="-" banned="-" hosts="-" up="-" hc ht ip
  state="$(container_state)"
  case "$state" in running) sc="$GRN"; label="RUNNING" ;; absent) sc="$GRY"; label="NOT INSTALLED" ;; *) sc="$RED"; label="${state^^}" ;; esac
  if [ "$state" = running ]; then
    up="$(fmt_uptime)"
    ram="$(docker stats --no-stream --format '{{.MemUsage}}' "$CONTAINER" 2>/dev/null | awk '{print $1}')"
    stats="$(counters)"
    [ -n "$stats" ] && IFS='|' read -r mode users subs banned hosts <<<"$stats"
  fi
  hc="$GRY"; ht="off"; if is_installed && [ "$(env_get HOST_ACCESS)" = 1 ]; then hc="$GRN"; ht="on"; fi
  ip="$(first_ip)"
  printf ' %s●%s BOT      %s%-13s%s %s●%s MODE    %s%s%s\n' "$TXT" "$RST" "$sc" "$label" "$RST" "$TXT" "$RST" "$CYN" "$mode" "$RST"
  printf ' %s●%s USERS    %s%-13s%s %s●%s PLANS   %s%s%s\n' "$TXT" "$RST" "$GRN" "$users" "$RST" "$TXT" "$RST" "$GRN" "$subs" "$RST"
  printf ' %s●%s SERVERS  %s%-13s%s %s●%s BANNED  %s%s%s\n' "$TXT" "$RST" "$GRN" "$hosts" "$RST" "$TXT" "$RST" "$GRN" "$banned" "$RST"
  printf ' %s●%s UPTIME   %s%-13s%s %s●%s RAM     %s%s%s\n' "$TXT" "$RST" "$CYN" "$up" "$RST" "$TXT" "$RST" "$CYN" "${ram:--}" "$RST"
  printf ' %s●%s THIS-SRV %s%-13s%s %s●%s IP      %s%s%s\n' "$TXT" "$RST" "$hc" "$ht" "$RST" "$TXT" "$RST" "$CYN" "${ip:--}" "$RST"
}

cmd_status() { banner; dashboard; rule; }

# ── doctor ───────────────────────────────────────────────────────────────────
cmd_doctor() {
  need_root doctor
  banner; title "Health check"
  local problems=0 tok state restarts who errs free_mb

  if have docker && docker info >/dev/null 2>&1; then ok "Docker is running"; else bad "Docker is not running (systemctl start docker)"; problems=$((problems + 1)); fi
  if docker compose version >/dev/null 2>&1; then ok "Docker Compose v2 available"; else bad "Docker Compose v2 is missing"; problems=$((problems + 1)); fi
  if is_installed; then ok "Installed in $SM_DIR"; else bad "Not installed (run: AX-Manager install)"; return 1; fi

  if [ "$(stat -c %a "$ENV_FILE" 2>/dev/null)" = 600 ]; then ok ".env is private (600)"; else warn ".env should be mode 600 — fixed"; chmod 600 "$ENV_FILE"; fi
  tok="$(env_get BOT_TOKEN)"
  if [[ "$tok" =~ ^[0-9]{6,}:[A-Za-z0-9_-]{30,}$ ]]; then ok "Bot token format is valid"; else bad "BOT_TOKEN looks invalid (AX-Manager settings)"; problems=$((problems + 1)); fi
  if [[ "$(env_get ADMIN_ID)" =~ ^[0-9]{5,}$ ]]; then ok "Admin ID is set"; else bad "ADMIN_ID is invalid"; problems=$((problems + 1)); fi
  if who="$(telegram_getme "$tok")" && [ -n "$who" ]; then ok "Telegram accepts the token (@$who)"; else warn "Cannot verify the token with Telegram (network or wrong token)"; fi

  state="$(container_state)"
  if [ "$state" = running ]; then
    ok "Container is running (up $(fmt_uptime))"
    restarts="$(docker inspect -f '{{.RestartCount}}' "$CONTAINER" 2>/dev/null || echo 0)"
    if [ "${restarts:-0}" -gt 3 ]; then warn "The container restarted $restarts times — check the logs"; problems=$((problems + 1)); fi
    if docker logs "$CONTAINER" 2>&1 | grep -q "started as @"; then ok "The bot connected to Telegram"; else warn "No 'started' line in the log yet"; fi
    errs="$(docker logs --tail 200 "$CONTAINER" 2>&1 | grep -cE ' (ERROR|CRITICAL) ' || true)"
    [ "${errs:-0}" -gt 0 ] && warn "$errs error lines in the recent log (AX-Manager logs)"
  else
    bad "Container state: $state"; problems=$((problems + 1))
    docker logs --tail 8 "$CONTAINER" 2>&1 | sed 's/^/      /'
  fi

  free_mb="$(df -Pm "$SM_DIR" | awk 'NR==2{print $4}')"
  if [ "${free_mb:-0}" -gt 300 ]; then ok "Disk space: ${free_mb} MB free"; else warn "Low disk space: ${free_mb} MB"; problems=$((problems + 1)); fi
  if have timedatectl; then
    if [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = yes ]; then ok "System clock is synchronized"; else warn "System clock is not NTP-synchronized"; fi
  fi

  if [ "$(env_get HOST_ACCESS)" = 1 ]; then
    printf '\n  %s"This server" access%s\n' "$BOLD" "$RST"
    if [ "$state" = running ]; then host_access_test || problems=$((problems + 1)); else warn "Start the bot first"; fi
  fi
  rule
  if [ "$problems" -eq 0 ]; then printf '  %s%sEverything looks healthy.%s\n' "$BOLD" "$GRN" "$RST"
  else printf '  %s%s%s problem(s) found.%s\n' "$BOLD" "$YEL" "$problems" "$RST"; fi
}

# ── lifecycle ────────────────────────────────────────────────────────────────
cmd_start()   { need_root start; need_installed; spin "Starting" dc up -d && wait_started && ok "Online"; }
cmd_stop()    { need_root stop; need_installed; spin "Stopping" dc stop; }
cmd_restart() { need_root restart; need_installed; spin "Restarting" dc restart && wait_started && ok "Online"; }
cmd_logs()    { need_installed; if [ "${1:-}" = "-f" ]; then docker logs -f --tail 100 "$CONTAINER"; else docker logs --tail 100 "$CONTAINER" 2>&1; fi; }

cmd_backup() {
  need_root backup; need_installed
  mkdir -p "$BACKUP_DIR"; chmod 700 "$BACKUP_DIR"
  local out; out="$BACKUP_DIR/servermanager-$(date +%Y%m%d-%H%M%S).tar.gz"
  ( umask 077; tar -C "$SM_DIR" -czf "$out" data .env .install.conf 2>/dev/null )
  ok "Saved $out ($(du -h "$out" | cut -f1))"
  find "$BACKUP_DIR" -name 'servermanager-*.tar.gz' -printf '%T@ %p\n' | sort -rn | tail -n +8 | cut -d' ' -f2- | xargs -r rm -f
  info "This archive contains your encryption key and settings — keep it private."
}

cmd_update() {
  need_root update; need_installed
  banner; title "Update"
  cmd_backup >/dev/null && ok "Backed up data and settings first"
  local mode; mode="$(conf_get MODE)"; mode="${mode:-image}"
  ensure_mtu
  dc down >/dev/null 2>&1 || true
  obtain_app "$mode"
  fix_permissions
  if start_and_verify; then ok "Updated and running"; else bad "The new version did not start. Your backup is in $BACKUP_DIR"; return 1; fi
  install_self
}

cmd_settings() {
  need_root settings; need_installed
  banner; title "Settings"
  local v choice
  printf '  %s1)%s Bot token         %s\n' "$CYN" "$RST" "$(env_get BOT_TOKEN | cut -d: -f1):••••"
  printf '  %s2)%s Admin ID          %s\n' "$CYN" "$RST" "$(env_get ADMIN_ID)"
  printf '  %s3)%s Display name      %s\n' "$CYN" "$RST" "$(env_get BOT_NAME)"
  printf '  %s4)%s Support username  %s\n' "$CYN" "$RST" "$(env_get SUPPORT_USERNAME)"
  printf '  %s5)%s Timezone          %s\n' "$CYN" "$RST" "$(env_get TZ)"
  printf '  %s6)%s Allowed private networks (CIDR)  %s\n' "$CYN" "$RST" "$(env_get ALLOWED_NETS)"
  printf '  %s0)%s Back\n\n' "$CYN" "$RST"
  choice="$(ask "Choose" "0")"
  case "$choice" in
    1) v="$(ask_secret "New bot token")"; if [[ "$v" =~ ^[0-9]{6,}:[A-Za-z0-9_-]{30,}$ ]]; then env_set BOT_TOKEN "$v"; else bad "Invalid token"; return 1; fi ;;
    2) v="$(ask "New admin ID")"; if [[ "$v" =~ ^[0-9]{5,}$ ]]; then env_set ADMIN_ID "$v"; else bad "Invalid ID"; return 1; fi ;;
    3) env_set BOT_NAME "$(clean_brand "$(ask "Display name" "$(env_get BOT_NAME)")")" ;;
    4) v="$(ask "Support username (empty to hide)" "$(env_get SUPPORT_USERNAME)")"
       if [[ -z "$v" || "$v" =~ ^@?[A-Za-z][A-Za-z0-9_]{4,31}$ ]]; then env_set SUPPORT_USERNAME "$v"; else bad "Invalid username"; return 1; fi ;;
    5) env_set TZ "$(ask "Timezone (e.g. Europe/Berlin)" "$(env_get TZ)")" ;;
    6) env_set ALLOWED_NETS "$(ask "Comma-separated CIDRs users may reach (e.g. 10.8.0.0/24)" "$(env_get ALLOWED_NETS)")" ;;
    *) return 0 ;;
  esac
  spin "Applying" dc up -d --force-recreate && wait_started && ok "Settings applied"
}

cmd_import_data() {
  need_root import-data; need_installed
  local src="${1:-}" k v
  [ -d "$src" ] && [ -f "$src/.env" ] || die "Usage: AX-Manager import-data /path/to/old/install   (the folder that holds .env and data/)"
  confirm "Replace this installation's settings and data with the ones from $src?" n || return 0
  dc stop >/dev/null 2>&1 || true
  for k in BOT_TOKEN ADMIN_ID BACKUP_PASSPHRASE SUPPORT_USERNAME TZ BLOCKED_IPS BACKUP_INTERVAL_HOURS MAX_LIVE_SESSIONS IDLE_TIMEOUT_MIN MAX_SESSION_HOURS; do
    v="$(grep -m1 "^$k=" "$src/.env" | cut -d= -f2-)"
    [ -n "$v" ] && env_set "$k" "$v"
  done
  if [ -d "$src/data" ]; then rm -rf "$DATA_DIR"; cp -a "$src/data" "$DATA_DIR"; ok "Copied data"; fi
  fix_permissions
  if start_and_verify; then ok "Imported — the bot is running with your previous data"; fi
}

cmd_uninstall() {
  need_root uninstall; is_installed || die "Nothing to uninstall."
  banner; title "Uninstall"
  confirm "Stop and remove the bot?" n || return 0
  [ "$(env_get HOST_ACCESS)" = 1 ] && host_access_disable
  dc down --rmi local >/dev/null 2>&1 || dc down >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  ok "Removed the container and network"
  if confirm "Also delete ALL data (users, saved servers, encryption key, settings)?" n; then
    rm -rf "$SM_DIR"; ok "Deleted $SM_DIR"
  else
    info "Kept $SM_DIR (data and settings). Delete it manually when you no longer need it."
  fi
  rm -f "$BIN_PATH" "$ALIAS_PATH"
  ok "Done"
}

# ── interactive control panel ────────────────────────────────────────────────
cmd_menu() {
  need_root
  is_installed || { cmd_install; return; }
  local c
  while :; do
    banner; dashboard; rule
    printf '\n'
    printf '  %s[1]%s Health check          %s[6]%s Settings\n' "$RED" "$RST" "$RED" "$RST"
    printf '  %s[2]%s Show logs             %s[7]%s This-server access\n' "$RED" "$RST" "$RED" "$RST"
    printf '  %s[3]%s Restart               %s[8]%s Local backup\n' "$RED" "$RST" "$RED" "$RST"
    printf '  %s[4]%s Stop / Start          %s[9]%s Uninstall\n' "$RED" "$RST" "$RED" "$RST"
    printf '  %s[5]%s Update                %s[0]%s Exit\n\n' "$RED" "$RST" "$RED" "$RST"
    c="$(ask "▸ Choose" "0")"
    NO_CLEAR=1
    case "$c" in
      1) cmd_doctor ;;
      2) cmd_logs ;;
      3) cmd_restart ;;
      4) if [ "$(container_state)" = running ]; then cmd_stop; else cmd_start; fi ;;
      5) cmd_update ;;
      6) cmd_settings ;;
      7) if [ "$(env_get HOST_ACCESS)" = 1 ]; then
           if confirm "\"This server\" access is ON. Disable it?" n; then host_access_disable; else host_access_test; fi
         else host_access_enable; fi ;;
      8) cmd_backup ;;
      9) cmd_uninstall; [ -f "$BIN_PATH" ] || exit 0 ;;
      0|"") exit 0 ;;
    esac
    NO_CLEAR=0
    printf '\n'
    if can_prompt; then printf '  %sPress Enter to continue…%s' "$DIM" "$RST" >/dev/tty; read -r _ </dev/tty || true; fi
  done
}

cmd_help() { sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//; /^─/d'; }

main() {
  case "${1:-menu}" in
    menu)        cmd_menu ;;
    install)     cmd_install ;;
    status)      cmd_status ;;
    doctor)      cmd_doctor ;;
    start)       cmd_start ;;
    stop)        cmd_stop ;;
    restart)     cmd_restart ;;
    logs)        shift; cmd_logs "${1:-}" ;;
    update)      cmd_update ;;
    settings)    cmd_settings ;;
    host-access) shift; cmd_host_access "${1:-status}" ;;
    backup)      cmd_backup ;;
    import-data) shift; cmd_import_data "${1:-}" ;;
    uninstall)   cmd_uninstall ;;
    version|-v|--version) echo "AX-Manager $SM_VERSION" ;;
    help|-h|--help) cmd_help ;;
    *) printf 'Unknown command: %s\n\n' "$1" >&2; cmd_help; exit 1 ;;
  esac
}

# Allow `source servermanager.sh` (tests) without running anything.
[ "${SM_SOURCE_ONLY:-0}" = 1 ] || main "$@"
