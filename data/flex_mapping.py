"""VRM expression → Source Engine flex name mapping.

VRM 1.0 defines 18 standard expression presets. After VRM import to Blender,
these become Shape Keys on the mesh. mesh_prepare._clean_shape_keys() strips
underscores from their names.

Source Engine uses flex controllers and flexes defined in VTA/QC.
GMod supports up to 96 flex controllers per model.

References:
  VRM spec: https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/expressions.md
  Source flex: https://developer.valvesoftware.com/wiki/Flex_animation
"""

import re

# ---------------------------------------------------------------------------
# VRM shape key name (post-underscore-removal, lowercase) → Source flex name
# ---------------------------------------------------------------------------
VRM_TO_FLEX: dict[str, str] = {
    # Emotions
    "happy":      "happy",
    "angry":      "angry",
    "sad":        "sad",
    "relaxed":    "relaxed",
    "surprised":  "surprised",
    "neutral":    "neutral",
    # Visemes (lip sync)
    "aa":         "aa",
    "ih":         "ih",
    "ou":         "ou",
    "ee":         "ee",
    "oh":         "oh",
    # Blink
    "blink":      "blink",
    "blinkleft":  "blink_left",
    "blinkright": "blink_right",
    # Gaze (look direction)
    "lookup":     "look_up",
    "lookdown":   "look_down",
    "lookleft":   "look_left",
    "lookright":  "look_right",
}

# Set of known VRM standard names for quick membership check
VRM_STANDARD_NAMES: frozenset[str] = frozenset(VRM_TO_FLEX.keys())

# ---------------------------------------------------------------------------
# Romaji (romanized Japanese) → Source flex name
# Common in VRC/Booth models that use romaji for shape key names.
# ---------------------------------------------------------------------------
ROMAJI_TO_FLEX: dict[str, str] = {
    # Visemes (vowels)
    "a": "aa", "i": "ih", "u": "ou", "e": "ee", "o": "oh",
    # Blink
    "mabataki": "blink", "winkl": "blink_left", "winkr": "blink_right",
    # Emotions
    "ikari": "angry", "kanasimi": "sad", "kanashimi": "sad",
    "nagomi": "relaxed", "odoroki": "surprised",
    "yorokobi": "happy", "warai": "happy",
    "majime": "neutral", "bikkuri": "surprised",
}

# ---------------------------------------------------------------------------
# Japanese Unicode → Source flex name
# Models with kanji/hiragana/katakana shape key names.
# ---------------------------------------------------------------------------
JAPANESE_TO_FLEX: dict[str, str] = {
    # Visemes
    "あ": "aa", "い": "ih", "う": "ou", "え": "ee", "お": "oh",
    # Blink
    "まばたき": "blink",
    "ウィンク": "blink_right", "ウィンク右": "blink_left",
    # Emotions
    "笑い": "happy", "にこり": "happy",
    "怒り": "angry",
    "困る": "sad", "悲しみ": "sad",
    "びっくり": "surprised",
    "なごみ": "relaxed",
    "真面目": "neutral",
}

# ---------------------------------------------------------------------------
# VRC / Booth / Unity community aliases → Source flex name
# ---------------------------------------------------------------------------
ALIAS_TO_FLEX: dict[str, str] = {
    # VRC viseme prefix
    "vrc.v_aa": "aa", "vrc.v_ih": "ih", "vrc.v_ou": "ou",
    "vrc.v_ee": "ee", "vrc.v_oh": "oh",
    # Common English aliases
    "smile": "happy", "joy": "happy", "fun": "happy",
    "sorrow": "sad", "close": "blink",
    "blinkl": "blink_left", "blinkr": "blink_right",
    # mouth_ prefix (Unity / VRC naming)
    "mouth_a-": "aa", "mouth_i-": "ih", "mouth_u-": "ou",
    "mouth_e-": "ee", "mouth_o-": "oh", "mouth_aa-": "aa",
    "mouith_a-": "aa",
}

# Shape key names to always skip (base/reference shapes, not expressions)
_SKIP_NAMES: frozenset[str] = frozenset({"basis", "base"})

# Maximum flex controllers supported by GMod
GMOD_FLEX_LIMIT = 96

# ---------------------------------------------------------------------------
# Dropdown items for flex target selection in UI.
# Format: (identifier, display_name, description)
# identifier is the Source Engine flex name stored in QC/VTA.
# 'NONE' = skip (don't export), 'CUSTOM' = user-defined name.
# ---------------------------------------------------------------------------
FLEX_TARGET_ITEMS: list[tuple[str, str, str]] = [
    ('NONE', "-- スキップ --", "エクスポートしない"),
    # --- Blink ---
    ('blink', "blink (瞬き)", "両目瞬き"),
    ('blink_left', "blink_left (左目瞬き)", "左目のみ瞬き"),
    ('blink_right', "blink_right (右目瞬き)", "右目のみ瞬き"),
    # --- Emotions ---
    ('happy', "happy (笑顔)", "笑顔・嬉しい"),
    ('angry', "angry (怒り)", "怒り"),
    ('sad', "sad (悲しみ)", "悲しい"),
    ('relaxed', "relaxed (リラックス)", "リラックス・穏やか"),
    ('surprised', "surprised (驚き)", "驚き"),
    ('neutral', "neutral (無表情)", "ニュートラル"),
    # --- Visemes (lip sync) ---
    ('aa', "aa (あ)", "口: あ"),
    ('ih', "ih (い)", "口: い"),
    ('ou', "ou (う)", "口: う"),
    ('ee', "ee (え)", "口: え"),
    ('oh', "oh (お)", "口: お"),
    # --- Look direction ---
    ('look_up', "look_up (上を見る)", "視線: 上"),
    ('look_down', "look_down (下を見る)", "視線: 下"),
    ('look_left', "look_left (左を見る)", "視線: 左"),
    ('look_right', "look_right (右を見る)", "視線: 右"),
    # --- Custom ---
    ('CUSTOM', "カスタム名...", "自由入力のflex名を使用"),
]

# Quick lookup: identifier → True (for checking if a target is valid)
_FLEX_TARGET_IDS: frozenset[str] = frozenset(
    item[0] for item in FLEX_TARGET_ITEMS
    if item[0] not in ('NONE', 'CUSTOM')
)


def sanitize_flex_name(name: str) -> str:
    """Convert a shape key name to a Source Engine-safe flex name.

    Rules:
    - Lowercase
    - Non-alphanumeric characters → underscore
    - Strip leading underscores/digits
    - Collapse consecutive underscores
    """
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    sanitized = re.sub(r'^[_0-9]+', '', sanitized)
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized.lower() or "flex"


def get_flex_target(shape_key_name: str) -> tuple[str, bool]:
    """Get the flex target enum identifier for a Blender shape key name.

    Checks multiple dictionaries in priority order:
      1. VRM standard English names (happy, blink, aa, ...)
      2. Romaji names (mabataki, ikari, a, i, u, ...)
      3. Japanese Unicode names (まばたき, 怒り, あ, ...)
      4. VRC/Booth community aliases (vrc.v_aa, smile, ...)
      5. Sanitized name matching known flex targets

    Parameters
    ----------
    shape_key_name : str
        Blender shape key name (post-underscore-removal by mesh_prepare).

    Returns
    -------
    tuple[str, bool]
        (flex_target_identifier, is_vrm_standard).
        Returns ('NONE', False) for unknown names.
    """
    key = shape_key_name.lower()

    # Priority 1: VRM standard English
    if key in VRM_TO_FLEX:
        return VRM_TO_FLEX[key], True

    # Priority 2: Romaji
    if key in ROMAJI_TO_FLEX:
        return ROMAJI_TO_FLEX[key], False

    # Priority 3: Japanese Unicode (use original case for kanji/kana)
    if shape_key_name in JAPANESE_TO_FLEX:
        return JAPANESE_TO_FLEX[shape_key_name], False

    # Priority 4: Community aliases
    if key in ALIAS_TO_FLEX:
        return ALIAS_TO_FLEX[key], False

    # Priority 5: Sanitized name matches a known target
    sanitized = sanitize_flex_name(shape_key_name)
    if sanitized in _FLEX_TARGET_IDS:
        return sanitized, False

    return 'NONE', False


def auto_assign_all(shape_key_name: str) -> tuple[str, str]:
    """Return (flex_target, custom_flex_name) for auto-assign-all mode.

    Known names → standard target, '' for custom_name.
    Unknown names → 'CUSTOM', sanitized name.
    Skip names (Base/Basis) → 'NONE', ''.
    """
    if shape_key_name.lower() in _SKIP_NAMES:
        return 'NONE', ''

    target, _ = get_flex_target(shape_key_name)
    if target != 'NONE':
        return target, ''

    # Unknown: assign as CUSTOM with sanitized name
    sanitized = sanitize_flex_name(shape_key_name)
    if not sanitized or sanitized == "flex":
        return 'NONE', ''
    return 'CUSTOM', sanitized
