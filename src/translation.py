"""
Pokemon name translations - English to Traditional Chinese (Official names).
"""

# Official Traditional Chinese names for Pokemon
# Based on Pokemon official Chinese translations
POKEMON_TRANSLATIONS = {
    # A
    "aegislash": "堅盾劍怪",
    "alakazam": "胡地",
    "arboliva": "奧利瓦",
    "archaludon": "鋁鋼龍",
    
    # B
    "barbaracle": "龜足巨鎧",
    "blaziken": "火焰雞",
    "blissey": "幸福蛋",
    
    # C
    "ceruledge": "蒼炎刃鬼",
    "clefairy": "皮皮",
    "crustle": "岩殿居蟹",
    
    # D
    "darmanitan": "達摩狒狒",
    "decidueye": "狙射樹梟",
    "diancie": "蒂安希",
    "diancie-mega": "超級蒂安希",
    "diggersby": "掘掘兔",
    "dipplin": "裹蜜蟲",
    "dragapult": "多龍巴魯托",
    "dudunsparce": "土龍節節",
    "dusknoir": "黑夜魔靈",
    
    # E
    "eelektross": "麻麻鰻魚王",
    "eelektross-mega": "超級麻麻鰻魚王",
    "empoleon": "帝王拿波",
    
    # F
    "feraligatr": "大力鱷",
    "feraligatr-mega": "超級大力鱷",
    "flareon": "火伊布",
    "froslass": "雪妖女",
    "froslass-mega": "超級雪妖女",
    
    # G
    "garchomp": "烈咬陸鯊",
    "gengar": "耿鬼",
    "gengar-mega": "超級耿鬼",
    "genesect": "蓋諾賽克特",
    "greninja": "甲賀忍蛙",
    "grimmsnarl": "長毛巨魔",
    "gumshoos": "貓鼬探長",
    
    # H
    "hariyama": "鐵掌力士",
    "honchkrow": "烏鴉頭頭",
    "hydreigon": "三首惡龍",
    
    # J
    "jellicent": "胖嘟嘟",
    
    # K
    "kangaskhan": "袋獸",
    "kangaskhan-mega": "超級袋獸",
    
    # L
    "latias": "拉帝亞斯",
    "leafeon": "葉伊布",
    "lopunny": "長耳兔",
    "lopunny-mega": "超級長耳兔",
    "lucario": "路卡利歐",
    "lucario-mega": "超級路卡利歐",
    
    # M
    "manectric": "雷電獸",
    "manectric-mega": "超級雷電獸",
    "meganium": "大竺葵",
    "meganium-mega": "超級大竺葵",
    "meowth": "喵喵",
    "metagross": "巨金怪",
    "mewtwo": "超夢",
    "munkidori": "願增猿",
    
    # N
    "noctowl": "貓頭夜鷹",
    
    # O
    "ogerpon": "厄鬼椪",
    "ogerpon-wellspring": "厄鬼椪(水井)",
    "okidogi": "夠讚狗",
    
    # P
    "pecharunt": "桃歹郎",
    "porygon-z": "多邊獸Z",
    "porygon2": "多邊獸2",
    
    # R
    "raging-bolt": "怒雷鞭",
    "rillaboom": "轟擂金剛猩",
    "roserade": "羅絲雷朵",
    
    # S
    "sharpedo": "巨牙鯊",
    "sharpedo-mega": "超級巨牙鯊",
    "slowbro": "呆殼獸",
    "slowbro-mega": "超級呆殼獸",
    "slowking": "呆呆王",
    "solrock": "太陽岩",
    "spidops": "操陷蛛",
    "starmie": "寶石海星",
    "starmie-mega": "超級寶石海星",
    
    # T
    "thwackey": "啪咚猴",
    "toxtricity": "顫弦蠑螈",
    
    # V
    "venusaur": "妙蛙花",
    "venusaur-mega": "超級妙蛙花",
    "vileplume": "霸王花",
    "vivillon": "彩粉蝶",
    
    # Y
    "yanmega": "遠古巨蜓",
    
    # Z
    "zoroark": "索羅亞克",
}


def translate_pokemon_name(english_name: str) -> str:
    """
    Translate a Pokemon name from English to Traditional Chinese.
    
    Args:
        english_name: The English name of the Pokemon (lowercase)
    
    Returns:
        Traditional Chinese name, or original if not found
    """
    if not english_name:
        return english_name
    
    # Normalize the name
    name_lower = english_name.lower().strip()
    
    # Direct lookup
    if name_lower in POKEMON_TRANSLATIONS:
        return POKEMON_TRANSLATIONS[name_lower]
    
    return english_name


def translate_archetype(archetype: str) -> str:
    """
    Translate a deck archetype (which may contain multiple Pokemon names).
    
    Args:
        archetype: The archetype string, e.g., "dragapult / dusknoir"
    
    Returns:
        Translated archetype string
    """
    if not archetype or archetype == "Unknown":
        return archetype
    
    # Split by common separators
    parts = archetype.split(" / ")
    translated_parts = []
    
    for part in parts:
        translated = translate_pokemon_name(part.strip())
        translated_parts.append(translated)
    
    return " / ".join(translated_parts)
