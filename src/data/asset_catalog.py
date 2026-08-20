"""Curated assets that are not covered reliably by the index-based seed.

The main universe comes from the S&P 500 and S&P/TSX Composite.  Cryptoassets
have no index listing in those sources, and many useful REITs sit outside the
large-cap indices, so they live in this small, explicit supplement.  Yahoo
symbols are stored here instead of guessed at runtime (notably ``BTC-CAD`` and
Canadian trust units such as ``MRG-UN.TO``).
"""


def _crypto(symbol: str, name: str, yahoo_symbol: str | None = None) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "sector": "Cryptoassets",
        "industry": "Cryptocurrency",
        "exchange": "CRYPTO",
        "currency": "CAD",
        "yahoo_symbol": yahoo_symbol or f"{symbol}-CAD",
        "country": "Global",
    }


CRYPTO_ASSETS = (
    _crypto("BTC", "Bitcoin"),
    _crypto("ETH", "Ethereum"),
    _crypto("USDT", "Tether"),
    _crypto("XRP", "XRP"),
    _crypto("BNB", "BNB"),
    _crypto("SOL", "Solana"),
    _crypto("USDC", "USD Coin"),
    _crypto("DOGE", "Dogecoin"),
    _crypto("ADA", "Cardano"),
    _crypto("TRX", "TRON"),
    _crypto("AVAX", "Avalanche"),
    _crypto("LINK", "Chainlink"),
    _crypto("BCH", "Bitcoin Cash"),
    _crypto("XLM", "Stellar"),
    _crypto("HBAR", "Hedera"),
    _crypto("LTC", "Litecoin"),
    _crypto("SHIB", "Shiba Inu"),
    _crypto("DOT", "Polkadot"),
    _crypto("DAI", "Dai"),
    _crypto("AAVE", "Aave"),
    _crypto("ICP", "Internet Computer"),
    _crypto("ETC", "Ethereum Classic"),
    _crypto("FIL", "Filecoin"),
    _crypto("ATOM", "Cosmos"),
    _crypto("ALGO", "Algorand"),
    _crypto("VET", "VeChain"),
    _crypto("MKR", "Maker"),
    _crypto("CRO", "Cronos"),
    _crypto("RUNE", "THORChain"),
    _crypto("XMR", "Monero"),
    _crypto("EOS", "EOS"),
    _crypto("XTZ", "Tezos"),
    _crypto("THETA", "Theta Network"),
    _crypto("MANA", "Decentraland"),
    _crypto("SAND", "The Sandbox"),
    _crypto("EGLD", "MultiversX"),
    _crypto("QNT", "Quant"),
    _crypto("FLOW", "Flow"),
    _crypto("BSV", "Bitcoin SV"),
    _crypto("NEO", "Neo"),
    _crypto("IOTA", "IOTA"),
    _crypto("ZEC", "Zcash"),
    _crypto("DASH", "Dash"),
    _crypto("SNX", "Synthetix"),
    _crypto("CRV", "Curve DAO"),
)


def _reit(
    symbol: str,
    name: str,
    exchange: str,
    industry: str,
    yahoo_symbol: str | None = None,
) -> dict:
    currency = "CAD" if exchange == "TSX" else "USD"
    if yahoo_symbol is None:
        yahoo_symbol = f"{symbol.replace('.', '-')}.TO" if exchange == "TSX" else symbol
    return {
        "symbol": symbol,
        "name": name,
        "sector": "Real Estate",
        "industry": industry,
        "exchange": exchange,
        "currency": currency,
        "yahoo_symbol": yahoo_symbol,
        "country": "Canada" if exchange == "TSX" else "United States",
    }


# Large index constituents are intentionally repeated here.  The upsert is
# idempotent, and keeping a self-contained REIT catalog means a temporary
# Wikipedia/index change cannot remove this asset class from a fresh install.
REIT_ASSETS = (
    # Canada
    _reit("AP.UN", "Allied Properties REIT", "TSX", "REIT - Office"),
    _reit("BEI.UN", "Boardwalk REIT", "TSX", "REIT - Residential"),
    _reit("CAR.UN", "Canadian Apartment Properties REIT", "TSX", "REIT - Residential"),
    _reit("CHP.UN", "Choice Properties REIT", "TSX", "REIT - Retail"),
    _reit("CRR.UN", "Crombie REIT", "TSX", "REIT - Diversified"),
    _reit("CRT.UN", "CT REIT", "TSX", "REIT - Retail"),
    _reit("CSH.UN", "Chartwell Retirement Residences", "TSX", "REIT - Healthcare"),
    _reit("DIR.UN", "Dream Industrial REIT", "TSX", "REIT - Industrial"),
    _reit("D.UN", "Dream Office REIT", "TSX", "REIT - Office"),
    _reit("FCR.UN", "First Capital REIT", "TSX", "REIT - Retail"),
    _reit("GRT.UN", "Granite REIT", "TSX", "REIT - Industrial"),
    _reit("HR.UN", "H&R REIT", "TSX", "REIT - Diversified"),
    _reit("KMP.UN", "Killam Apartment REIT", "TSX", "REIT - Residential"),
    _reit("MRG.UN", "Morguard North American Residential REIT", "TSX", "REIT - Residential"),
    _reit("PLZ.UN", "Plaza Retail REIT", "TSX", "REIT - Retail"),
    _reit("PMZ.UN", "Primaris REIT", "TSX", "REIT - Retail"),
    _reit("REI.UN", "RioCan REIT", "TSX", "REIT - Retail"),
    _reit("SGR.UN", "Slate Grocery REIT", "TSX", "REIT - Retail"),
    _reit("SRU.UN", "SmartCentres REIT", "TSX", "REIT - Retail"),
    # United States
    _reit("ADC", "Agree Realty", "US", "REIT - Retail"),
    _reit("AMT", "American Tower", "US", "REIT - Specialty"),
    _reit("ARE", "Alexandria Real Estate Equities", "US", "REIT - Office"),
    _reit("AVB", "AvalonBay Communities", "US", "REIT - Residential"),
    _reit("BXP", "BXP", "US", "REIT - Office"),
    _reit("CCI", "Crown Castle", "US", "REIT - Specialty"),
    _reit("CPT", "Camden Property Trust", "US", "REIT - Residential"),
    _reit("CUBE", "CubeSmart", "US", "REIT - Self Storage"),
    _reit("DLR", "Digital Realty", "US", "REIT - Data Centers"),
    _reit("EPR", "EPR Properties", "US", "REIT - Experiential"),
    _reit("EPRT", "Essential Properties Realty Trust", "US", "REIT - Retail"),
    _reit("EQIX", "Equinix", "US", "REIT - Data Centers"),
    _reit("EQR", "Equity Residential", "US", "REIT - Residential"),
    _reit("ESS", "Essex Property Trust", "US", "REIT - Residential"),
    _reit("EXR", "Extra Space Storage", "US", "REIT - Self Storage"),
    _reit("FR", "First Industrial Realty Trust", "US", "REIT - Industrial"),
    _reit("FRT", "Federal Realty Investment Trust", "US", "REIT - Retail"),
    _reit("GLPI", "Gaming and Leisure Properties", "US", "REIT - Gaming"),
    _reit("INVH", "Invitation Homes", "US", "REIT - Residential"),
    _reit("IRM", "Iron Mountain", "US", "REIT - Specialty"),
    _reit("KIM", "Kimco Realty", "US", "REIT - Retail"),
    _reit("MAA", "Mid-America Apartment Communities", "US", "REIT - Residential"),
    _reit("NNN", "NNN REIT", "US", "REIT - Retail"),
    _reit("O", "Realty Income", "US", "REIT - Retail"),
    _reit("OHI", "Omega Healthcare Investors", "US", "REIT - Healthcare"),
    _reit("PLD", "Prologis", "US", "REIT - Industrial"),
    _reit("PSA", "Public Storage", "US", "REIT - Self Storage"),
    _reit("REG", "Regency Centers", "US", "REIT - Retail"),
    _reit("REXR", "Rexford Industrial Realty", "US", "REIT - Industrial"),
    _reit("SPG", "Simon Property Group", "US", "REIT - Retail"),
    _reit("STAG", "STAG Industrial", "US", "REIT - Industrial"),
    _reit("UDR", "UDR", "US", "REIT - Residential"),
    _reit("VICI", "VICI Properties", "US", "REIT - Gaming"),
    _reit("VTR", "Ventas", "US", "REIT - Healthcare"),
    _reit("WELL", "Welltower", "US", "REIT - Healthcare"),
    _reit("WPC", "W. P. Carey", "US", "REIT - Diversified"),
)


SUPPLEMENTAL_ASSETS = CRYPTO_ASSETS + REIT_ASSETS
