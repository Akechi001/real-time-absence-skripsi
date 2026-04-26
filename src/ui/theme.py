# src/ui/theme.py - Theme Manager untuk adaptive Light/Dark mode

import platform
import subprocess


# Cache untuk hasil deteksi dark mode
_dark_mode_cache = None


def _detect_dark_mode_raw():
    """Deteksi sistem dark mode (raw, tanpa cache)"""
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(
                ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0 and 'Dark' in result.stdout

        elif system == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0

        elif system == "Linux":
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
                capture_output=True,
                text=True,
                timeout=2
            )
            return 'dark' in result.stdout.lower()

    except Exception:
        pass

    return False


def detect_dark_mode():
    """Deteksi dark mode dengan caching - print sekali saja"""
    global _dark_mode_cache

    if _dark_mode_cache is None:
        _dark_mode_cache = _detect_dark_mode_raw()
        if _dark_mode_cache:
            print("🌙 Dark mode terdeteksi - menggunakan dark theme")
        else:
            print("☀️ Light mode terdeteksi - menggunakan light theme")

    return _dark_mode_cache


def is_macos():
    """Check apakah running di macOS"""
    return platform.system() == "Darwin"


# ========== LIGHT THEME ==========
LIGHT_THEME = {
    'bg_primary': '#f5f6fa',
    'bg_secondary': '#ffffff',
    'bg_card': '#ffffff',
    'bg_input': '#ffffff',

    'text_primary': '#2c3e50',
    'text_secondary': '#7f8c8d',
    'text_light': '#ffffff',
    'text_button': '#ffffff',

    'btn_green': '#52c485',
    'btn_green_text': '#ffffff',

    'btn_blue': '#5b9bd5',
    'btn_blue_text': '#ffffff',

    'btn_orange': '#e89d54',
    'btn_orange_text': '#ffffff',

    'btn_purple': '#a987d1',
    'btn_purple_text': '#ffffff',

    'btn_red': '#e07b6f',
    'btn_red_text': '#ffffff',

    'btn_gray': '#95a5a6',
    'btn_gray_text': '#ffffff',

    'border': '#dcdde1',

    'row_active': '#ffffff',
    'row_inactive': '#fadbd8',
    'row_no_template': '#fcf3cf',
    'row_selected': '#5b9bd5',

    'header_bg': '#5b9bd5',
    'header_fg': '#ffffff',
}


# ========== DARK THEME ==========
DARK_THEME = {
    'bg_primary': '#1e1e2e',
    'bg_secondary': '#2a2a3e',
    'bg_card': '#2a2a3e',
    'bg_input': '#363650',

    'text_primary': '#e0e0e0',
    'text_secondary': '#a0a0a0',
    'text_light': '#ffffff',
    'text_button': '#ffffff',

    'btn_green': '#3a8c5e',
    'btn_green_text': '#ffffff',

    'btn_blue': '#4a7ba5',
    'btn_blue_text': '#ffffff',

    'btn_orange': '#b87333',
    'btn_orange_text': '#ffffff',

    'btn_purple': '#7d5ba6',
    'btn_purple_text': '#ffffff',

    'btn_red': '#a0524a',
    'btn_red_text': '#ffffff',

    'btn_gray': '#5a6a7a',
    'btn_gray_text': '#e0e0e0',

    'border': '#3e3e5e',

    'row_active': '#2a2a3e',
    'row_inactive': '#4a2e2e',
    'row_no_template': '#4a4530',
    'row_selected': '#4a7ba5',

    'header_bg': '#4a7ba5',
    'header_fg': '#ffffff',
}


def get_colors():
    """Get color palette berdasarkan system mode (cached)"""
    if detect_dark_mode():
        return DARK_THEME
    else:
        return LIGHT_THEME


def get_button_colors(button_type='blue'):
    """Get button color pair (bg + text)"""
    colors = get_colors()
    return {
        'bg': colors[f'btn_{button_type}'],
        'fg': colors[f'btn_{button_type}_text'],
    }


def darken_color(hex_color, factor=0.85):
    """Darken hex color"""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)

    return f'#{r:02x}{g:02x}{b:02x}'


def lighten_color(hex_color, factor=1.15):
    """Lighten hex color"""
    hex_color = hex_color.lstrip('#')
    r = min(255, int(int(hex_color[0:2], 16) * factor))
    g = min(255, int(int(hex_color[2:4], 16) * factor))
    b = min(255, int(int(hex_color[4:6], 16) * factor))

    return f'#{r:02x}{g:02x}{b:02x}'


def hover_color(hex_color):
    """Auto-detect hover color berdasarkan mode"""
    if detect_dark_mode():
        return lighten_color(hex_color, 1.2)
    else:
        return darken_color(hex_color, 0.88)