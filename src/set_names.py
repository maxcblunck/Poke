"""
Maps every local set code (filename in data/cards/en/) to its
official English display name.
"""

SET_NAMES: dict[str, str] = {
    # ── Base / Wizards era ────────────────────────────────────────────
    "base1":      "Base Set",
    "base2":      "Jungle",
    "base3":      "Fossil",
    "base4":      "Base Set 2",
    "base5":      "Team Rocket",
    "base6":      "Legendary Collection",
    "basep":      "Base Set Promos",
    "bp":         "Best of Game",

    # ── Gym series ───────────────────────────────────────────────────
    "gym1":       "Gym Heroes",
    "gym2":       "Gym Challenge",

    # ── Neo series ───────────────────────────────────────────────────
    "neo1":       "Neo Genesis",
    "neo2":       "Neo Discovery",
    "neo3":       "Neo Revelation",
    "neo4":       "Neo Destiny",

    # ── e-Card / Expedition series ───────────────────────────────────
    "ecard1":     "Expedition Base Set",
    "ecard2":     "Aquapolis",
    "ecard3":     "Skyridge",
    "np":         "Nintendo Black Star Promos",

    # ── EX series ────────────────────────────────────────────────────
    "ex1":        "EX Ruby & Sapphire",
    "ex2":        "EX Sandstorm",
    "ex3":        "EX Dragon",
    "ex4":        "EX Team Magma vs Team Aqua",
    "ex5":        "EX Hidden Legends",
    "ex6":        "EX FireRed & LeafGreen",
    "ex7":        "EX Team Rocket Returns",
    "ex8":        "EX Deoxys",
    "ex9":        "EX Emerald",
    "ex10":       "EX Unseen Forces",
    "ex11":       "EX Delta Species",
    "ex12":       "EX Legend Maker",
    "ex13":       "EX Holon Phantoms",
    "ex14":       "EX Crystal Guardians",
    "ex15":       "EX Dragon Frontiers",
    "ex16":       "EX Power Keepers",
    "pop1":       "POP Series 1",
    "pop2":       "POP Series 2",
    "pop3":       "POP Series 3",
    "pop4":       "POP Series 4",
    "pop5":       "POP Series 5",
    "pop6":       "POP Series 6",
    "pop7":       "POP Series 7",
    "pop8":       "POP Series 8",
    "pop9":       "POP Series 9",

    # ── Diamond & Pearl series ───────────────────────────────────────
    "dp1":        "Diamond & Pearl",
    "dp2":        "Mysterious Treasures",
    "dp3":        "Secret Wonders",
    "dp4":        "Great Encounters",
    "dp5":        "Majestic Dawn",
    "dp6":        "Legends Awakened",
    "dp7":        "Stormfront",
    "dpp":        "Diamond & Pearl Promos",

    # ── Platinum series ──────────────────────────────────────────────
    "pl1":        "Platinum",
    "pl2":        "Rising Rivals",
    "pl3":        "Supreme Victors",
    "pl4":        "Arceus",

    # ── HeartGold & SoulSilver series ────────────────────────────────
    "col1":       "Call of Legends",
    "hgss1":      "HeartGold & SoulSilver",
    "hgss2":      "Unleashed",
    "hgss3":      "Undaunted",
    "hgss4":      "Triumphant",
    "hsp":        "HGSS Promos",

    # ── Black & White series ─────────────────────────────────────────
    "bw1":        "Black & White",
    "bw2":        "Emerging Powers",
    "bw3":        "Noble Victories",
    "bw4":        "Next Destinies",
    "bw5":        "Dark Explorers",
    "bw6":        "Dragons Exalted",
    "bw7":        "Boundaries Crossed",
    "bw8":        "Plasma Storm",
    "bw9":        "Plasma Freeze",
    "bw10":       "Plasma Blast",
    "bw11":       "Legendary Treasures",
    "bwp":        "Black & White Promos",
    "dv1":        "Dragon Vault",
    "dc1":        "Dragon Collection",

    # ── XY series ────────────────────────────────────────────────────
    "xy0":        "Kalos Starter Set",
    "xy1":        "XY",
    "xy2":        "Flashfire",
    "xy3":        "Furious Fists",
    "xy4":        "Phantom Forces",
    "xy5":        "Primal Clash",
    "xy6":        "Roaring Skies",
    "xy7":        "Ancient Origins",
    "xy8":        "BREAKthrough",
    "xy9":        "BREAKpoint",
    "xy10":       "Fates Collide",
    "xy11":       "Steam Siege",
    "xy12":       "Evolutions",
    "xyp":        "XY Promos",
    "g1":         "Generations",
    "dc1":        "Double Crisis",
    "det1":       "Detective Pikachu",
    "fut20":      "Future (2020)",

    # ── Sun & Moon series ────────────────────────────────────────────
    "sm1":        "Sun & Moon",
    "sm2":        "Guardians Rising",
    "sm3":        "Burning Shadows",
    "sm35":       "Shining Legends",
    "sm4":        "Crimson Invasion",
    "sm5":        "Ultra Prism",
    "sm6":        "Forbidden Light",
    "sm7":        "Celestial Storm",
    "sm75":       "Dragon Majesty",
    "sm8":        "Lost Thunder",
    "sm9":        "Team Up",
    "sm10":       "Unbroken Bonds",
    "sm11":       "Unified Minds",
    "sm115":      "Hidden Fates",
    "sm12":       "Cosmic Eclipse",
    "sma":        "SM Black Star Promos",
    "smp":        "Sun & Moon Promos",

    # ── Sword & Shield series ────────────────────────────────────────
    "swsh1":      "Sword & Shield",
    "swsh2":      "Rebel Clash",
    "swsh3":      "Darkness Ablaze",
    "swsh35":     "Champion's Path",
    "swsh4":      "Vivid Voltage",
    "swsh45":     "Shining Fates",
    "swsh45sv":   "Shining Fates: Shiny Vault",
    "swsh5":      "Battle Styles",
    "swsh6":      "Chilling Reign",
    "swsh7":      "Evolving Skies",
    "swsh8":      "Fusion Strike",
    "swsh9":      "Brilliant Stars",
    "swsh9tg":    "Brilliant Stars: Trainer Gallery",
    "swsh10":     "Astral Radiance",
    "swsh10tg":   "Astral Radiance: Trainer Gallery",
    "swsh11":     "Lost Origin",
    "swsh11tg":   "Lost Origin: Trainer Gallery",
    "swsh12":     "Silver Tempest",
    "swsh12tg":   "Silver Tempest: Trainer Gallery",
    "swsh12pt5":  "Crown Zenith",
    "swsh12pt5gg":"Crown Zenith: Galarian Gallery",
    "swshp":      "Sword & Shield Promos",

    # ── Scarlet & Violet series ──────────────────────────────────────
    "sv1":        "Scarlet & Violet",
    "sv2":        "Paldea Evolved",
    "sv3":        "Obsidian Flames",
    "sv3pt5":     "151",
    "sv4":        "Paradox Rift",
    "sv4pt5":     "Paldean Fates",
    "sv5":        "Temporal Forces",
    "sv6":        "Twilight Masquerade",
    "sv6pt5":     "Shrouded Fable",
    "sv7":        "Stellar Crown",
    "sv8":        "Surging Sparks",
    "sv8pt5":     "Prismatic Evolutions",
    "sv9":        "Journey Together",
    "sv10":       "Destined Rivals",
    "sve":        "Scarlet & Violet Energies",
    "svp":        "Scarlet & Violet Promos",

    # ── Mega Evolution series ────────────────────────────────────────
    "me1":        "Mega Evolution: Blazing Skies",
    "me2":        "Mega Evolution: Phantasmal Flames",
    "me2pt5":     "Mega Evolution: Ascended Heroes",
    "me3":        "Mega Evolution: Perfect Order",
    "me4":        "Mega Evolution: Chaos Rising",

    # ── Special / promo sets ─────────────────────────────────────────
    "cel25":      "Celebrations",
    "cel25c":     "Celebrations: Classic Collection",
    "pgo":        "Pokémon GO",
    "ru1":        "Roaring Skies",
    "si1":        "Southern Islands",
    "rsv10pt5":   "Scarlet & Violet 10.5",
    "zsv10pt5":   "Scarlet & Violet 10.5 (Alt)",
    "tk1a":       "Trading Card Game Classic (Set A)",
    "tk1b":       "Trading Card Game Classic (Set B)",
    "tk2a":       "Trading Card Game Classic 2 (Set A)",
    "tk2b":       "Trading Card Game Classic 2 (Set B)",

    # ── McDonald's promos ────────────────────────────────────────────
    "mcd11":      "McDonald's 2011",
    "mcd12":      "McDonald's 2012",
    "mcd14":      "McDonald's 2014",
    "mcd15":      "McDonald's 2015",
    "mcd16":      "McDonald's 2016",
    "mcd17":      "McDonald's 2017",
    "mcd18":      "McDonald's 2018",
    "mcd19":      "McDonald's 2019",
    "mcd21":      "McDonald's 2021",
    "mcd22":      "McDonald's 2022",
}


def get_set_name(set_code: str) -> str:
    """Return display name for a set code, falling back to the code itself."""
    return SET_NAMES.get(set_code, set_code)
