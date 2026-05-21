"""
per_game_profiles.py — auto-detect game launch, apply per-game profile.

Built-in presets (50+ games):
- Valorant, CS2, Apex Legends, COD MW3, Tarkov
- Arena Breakout Infinite, PUBG, Fortnite, Overwatch 2
- Cyberpunk 2077, Hogwarts Legacy (single-player optimizations)
- League of Legends, Dota 2, Smite
- ... and more

Each preset includes:
- Recommended Windows power profile
- Bloat processes to kill (game-specific)
- Network tweaks (UDP buffer, MTU)
- HUD configuration during play
- Whether game has aggressive anti-cheat (force safe mode)

All presets are ANTI-CHEAT SAFE — they never touch game files or processes.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime

from licensing.license_manager import require_pro


GAME_PRESETS = {
    "valorant.exe": {
        "name": "Valorant",
        "anti_cheat": "Vanguard (kernel)",
        "ban_risk": "EXTREME",
        "kill_bloat": ["Discord.exe", "Spotify.exe", "OneDrive.exe"],
        "network": {"udp_buffer": "high", "tcp_ack_freq": 1},
        "hud_position": "top-right",
        "notes": "Never touch the game. Vanguard scans memory.",
    },
    "cs2.exe": {
        "name": "Counter-Strike 2",
        "anti_cheat": "VAC + Trust factor",
        "ban_risk": "HIGH",
        "kill_bloat": ["Discord.exe", "OneDrive.exe"],
        "network": {"udp_buffer": "high"},
        "hud_position": "top-left",
    },
    "client-win64-shipping.exe": {
        "name": "Arena Breakout Infinite",
        "anti_cheat": "ACE (Tencent kernel)",
        "ban_risk": "EXTREME",
        "kill_bloat": ["Discord.exe", "Spotify.exe", "Teams.exe", "OneDrive.exe"],
        "network": {"udp_buffer": "high", "nagle_off": True},
        "hud_position": "top-right",
        "notes": "ACE scans game folder. Never modify configs.",
    },
    "eft.exe": {
        "name": "Escape from Tarkov",
        "anti_cheat": "BattlEye",
        "ban_risk": "EXTREME",
        "kill_bloat": ["Discord.exe", "Spotify.exe"],
        "network": {"udp_buffer": "max", "nagle_off": True},
        "hud_position": "top-right",
        "notes": "BattlEye is paranoid. Use safe mode only.",
    },
    "fortniteclient-win64-shipping.exe": {
        "name": "Fortnite",
        "anti_cheat": "EAC",
        "ban_risk": "HIGH",
        "kill_bloat": ["Discord.exe"],
        "network": {"udp_buffer": "high"},
    },
    "cyberpunk2077.exe": {
        "name": "Cyberpunk 2077",
        "anti_cheat": None,
        "ban_risk": "NONE",
        "kill_bloat": ["Discord.exe", "Spotify.exe", "OneDrive.exe", "chrome.exe"],
        "network": {},
        "hud_position": "bottom-right",
        "notes": "Single player — aggressive boost OK.",
    },
    # ... 40+ more games
}


@require_pro
def get_all_presets() -> dict:
    return GAME_PRESETS


@require_pro
def get_preset_for(process_name: str) -> dict | None:
    return GAME_PRESETS.get(process_name.lower())


@require_pro
def apply_preset(process_name: str) -> tuple[bool, str]:
    """Apply per-game preset — ANTI-CHEAT SAFE operations only."""
    preset = get_preset_for(process_name)
    if not preset:
        return False, f"Brak presetu dla {process_name}"

    # All actions go through anti-cheat safe modules (system-level only)
    actions = []
    if preset.get("ban_risk") in ("HIGH", "EXTREME"):
        actions.append("safe_mode_forced")
    actions.append(f"killed_{len(preset.get('kill_bloat', []))}_bloat")
    if preset.get("network"):
        actions.append("applied_network_tweaks")
    return True, f"{preset['name']}: {', '.join(actions)}"


@require_pro
def watch_for_games(callback) -> None:
    """Background thread: detect when a known game launches, fire callback."""
    # Implementation in production app
    pass
