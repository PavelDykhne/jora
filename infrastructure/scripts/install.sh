#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# OpenClaw Job Hunter Agent — Installer
# Run as non-root user with sudo access.
# ============================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# --- Pre-flight ---
preflight() {
    info "Pre-flight checks..."
    if [ "$(id -u)" -eq 0 ]; then
        error "Do NOT run as root. Use a dedicated user with sudo."
        exit 1
    fi
    info "User: $(whoami) | OS: $(uname -s) | Project: ${PROJECT_DIR}"
}

# --- System deps ---
install_deps() {
    info "Installing system packages..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq curl wget git jq build-essential > /dev/null
}

# --- Docker ---
install_docker() {
    if command -v docker &> /dev/null; then
        info "Docker OK: $(docker --version)"
    else
        info "Installing Docker..."
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker "$USER"
        warn "Added $(whoami) to docker group. Re-login may be needed."
    fi
}

# --- Node.js ---
install_node() {
    if command -v node &> /dev/null && node -v | grep -q "^v2[2-9]"; then
        info "Node.js OK: $(node -v)"
    else
        info "Installing Node.js 22..."
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - > /dev/null
        sudo apt-get install -y -qq nodejs > /dev/null
    fi
}

# --- OpenClaw ---
install_openclaw() {
    if command -v openclaw &> /dev/null; then
        info "OpenClaw OK"
    else
        info "Installing OpenClaw..."
        curl -fsSL https://get.openclaw.ai | bash
        warn "Run 'openclaw setup' to configure (Anthropic key, Telegram channel)."
    fi
}

# --- Workspace ---
setup_workspace() {
    info "Setting up workspace..."
    mkdir -p "${PROJECT_DIR}/workspace/jobs/applications"

    # Copy template files if not present
    for f in "${PROJECT_DIR}/templates/"*.example; do
        [ -f "$f" ] || continue
        target="${PROJECT_DIR}/workspace/jobs/$(basename "$f" .example)"
        if [ ! -f "$target" ]; then
            cp "$f" "$target"
            info "  Created: $(basename "$target")"
        fi
    done
}

# --- .env ---
setup_env() {
    local env_file="${PROJECT_DIR}/infrastructure/.env"

    if [ -f "$env_file" ]; then
        warn ".env exists, skipping."
        return
    fi

    cp "${PROJECT_DIR}/infrastructure/.env.template" "$env_file"

    echo ""
    info "Configure credentials:"
    read -rp "  Telegram Bot Token: " tg_token
    read -rp "  Telegram Chat ID:   " tg_chat_id
    read -rp "  Anthropic API Key:  " anthropic_key

    sed -i "s|^TG_BOT_TOKEN=.*|TG_BOT_TOKEN=${tg_token}|" "$env_file"
    sed -i "s|^TG_CHAT_ID=.*|TG_CHAT_ID=${tg_chat_id}|" "$env_file"
    sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${anthropic_key}|" "$env_file"

    chmod 600 "$env_file"
    info ".env configured"
}

# --- Scanner config ---
setup_scanner_config() {
    info "Setting up scanner config..."
    local scanner_cfg="${PROJECT_DIR}/scanner/config/default.json"

    if [ -f "$scanner_cfg" ] && [ ! -f "${scanner_cfg}.template" ]; then
        info "Scanner config already in place."
        return
    fi

    if [ -f "${scanner_cfg}.template" ] && [ ! -f "$scanner_cfg" ]; then
        # Read TG creds from .env
        local env_file="${PROJECT_DIR}/infrastructure/.env"
        local tg_token tg_chat_id
        tg_token=$(grep "^TG_BOT_TOKEN=" "$env_file" | cut -d= -f2)
        tg_chat_id=$(grep "^TG_CHAT_ID=" "$env_file" | cut -d= -f2)

        # Create config from template
        sed "s|YOUR_BOT_TOKEN_HERE|${tg_token}|g; s|YOUR_CHAT_ID_HERE|${tg_chat_id}|g" \
            "${scanner_cfg}.template" > "$scanner_cfg"
        info "Scanner config created from template."
    fi
}

# --- Skills ---
install_skills() {
    info "Installing OpenClaw skills..."
    local skills_dir
    skills_dir="$(openclaw config get skillsDir 2>/dev/null || echo "${HOME}/.openclaw/workspace/skills")"
    mkdir -p "$skills_dir"

    for skill in "${PROJECT_DIR}/skills/"*/; do
        local name
        name="$(basename "$skill")"
        cp -r "$skill" "${skills_dir}/${name}"
    done
    info "Skills installed: $(ls "${PROJECT_DIR}/skills/" | tr '\n' ' ')"
}

# --- Docker services ---
start_services() {
    info "Starting Docker services..."
    cd "${PROJECT_DIR}/infrastructure"
    docker compose up -d --build
    sleep 10
    bash scripts/healthcheck.sh || warn "Some services may still be starting."
}

# --- Firewall ---
setup_firewall() {
    if command -v ufw &> /dev/null; then
        info "Configuring firewall..."
        sudo ufw allow OpenSSH
        sudo ufw --force enable
    fi
}

# --- Summary ---
summary() {
    echo ""
    echo "============================================================"
    info "✅ Installation complete!"
    echo "============================================================"
    echo ""
    echo "  Project: ${PROJECT_DIR}"
    echo ""
    echo "  Next steps:"
    echo "  1. cd ${PROJECT_DIR}/infrastructure && make status"
    echo "  2. Open Telegram → send your bot: Ищи вакансии Head of QA"
    echo ""
    echo "  Useful commands:"
    echo "    make logs          — follow logs"
    echo "    make backup        — backup MongoDB"
    echo "    make update        — pull & restart"
    echo "    make health        — health check"
    echo ""
    echo "============================================================"
}

# --- Main ---
main() {
    echo ""
    echo "🦞 OpenClaw Job Hunter Agent — Installer"
    echo "============================================================"

    preflight
    install_deps
    install_docker
    install_node
    install_openclaw
    setup_workspace
    setup_env
    setup_scanner_config
    install_skills
    setup_firewall
    start_services
    summary
}

main "$@"
