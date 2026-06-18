"""
Blockchain Forensics & Crypto Wallet Tracer
============================================
Traces cryptocurrency wallets across Bitcoin, Ethereum, BNB Chain, and TRON.
Uses 100% free public blockchain APIs (no API key required for basic use):
  - Blockchain.info (Bitcoin)
  - Etherscan.io (Ethereum — 5 req/s free)
  - BscScan.com (BNB Chain)
  - Tronscan.org (TRON / USDT-TRC20)
  - Blockchair.com (multi-chain)

Detects:
  - Total funds stolen (USD equivalent)
  - Transaction history and flow
  - Exchange wallet tags (Binance, Coinbase, WazirX, etc.)
  - Mixing / tumbling patterns (money laundering detection)
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from nciia.utils import get_logger

logger = get_logger(__name__)

# ── Known exchange / scam wallet labels ──────────────────────────────────────
KNOWN_LABELS: dict[str, str] = {
    # Exchanges (withdraw from scammer → police can get KYC)
    "3E35SzYZuAeURc1puMLPZhX9eyNsknwuae": "Binance Hot Wallet",
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s": "Binance Cold Wallet",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance Exchange",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken Exchange",
    "0xa910f92acdaf488fa6ef02174fb86208ad7722ba": "OKX Exchange",
    "TBbVB6Se3PrqKhBa2kp2kJRF1gXG7PFCVf": "Binance TRON",
}

# ── Mixer / tumbler patterns ───────────────────────────────────────────────────
MIXER_PATTERNS = [
    r"chipmixer", r"wasabi", r"joinmarket", r"coinjoin",
    r"tornado", r"tornado\.cash", r"blender", r"sinbad",
]


@dataclass
class Transaction:
    hash:       str
    from_addr:  str
    to_addr:    str
    value_usd:  float
    value_crypto: str
    timestamp:  str
    chain:      str
    label:      str = ""


@dataclass
class WalletReport:
    address:        str
    chain:          str           = "Unknown"
    balance_usd:    float         = 0.0
    balance_crypto: str           = ""
    total_received: float         = 0.0
    total_sent:     float         = 0.0
    tx_count:       int           = 0
    first_seen:     str           = ""
    last_seen:      str           = ""
    label:          str           = ""           # known exchange tag
    is_exchange:    bool          = False
    mixer_detected: bool          = False
    risk_score:     int           = 0
    risk_flags:     list[str]     = field(default_factory=list)
    transactions:   list[Transaction] = field(default_factory=list)
    connected_wallets: list[str]  = field(default_factory=list)
    errors:         list[str]     = field(default_factory=list)
    analyzed_at:    float         = field(default_factory=time.time)


def _detect_chain(address: str) -> str:
    """Auto-detect blockchain from address format."""
    addr = address.strip()
    if re.match(r'^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$', addr):
        return "Bitcoin"
    if re.match(r'^0x[a-fA-F0-9]{40}$', addr):
        return "Ethereum"  # or BSC (same format)
    if re.match(r'^T[a-zA-Z0-9]{33}$', addr):
        return "TRON"
    if re.match(r'^[a-zA-Z0-9]{26,35}$', addr) and addr.startswith('X'):
        return "XRP"
    return "Unknown"


async def _trace_bitcoin(client: httpx.AsyncClient, address: str, report: WalletReport) -> None:
    """Trace Bitcoin wallet using blockchain.info (free)."""
    try:
        r = await client.get(
            f"https://blockchain.info/rawaddr/{address}",
            params={"limit": 50},
            timeout=15,
        )
        if r.status_code != 200:
            report.errors.append(f"Bitcoin API: HTTP {r.status_code}")
            return
        data = r.json()

        # Get BTC price
        price_r = await client.get("https://blockchain.info/ticker", timeout=8)
        btc_price = 0.0
        if price_r.status_code == 200:
            btc_price = price_r.json().get("USD", {}).get("last", 0.0)

        satoshi_to_btc = 1e-8
        balance_btc    = data.get("final_balance", 0) * satoshi_to_btc
        received_btc   = data.get("total_received", 0) * satoshi_to_btc
        sent_btc       = data.get("total_sent", 0) * satoshi_to_btc

        report.balance_crypto = f"{balance_btc:.8f} BTC"
        report.balance_usd    = round(balance_btc * btc_price, 2)
        report.total_received = round(received_btc * btc_price, 2)
        report.total_sent     = round(sent_btc * btc_price, 2)
        report.tx_count       = data.get("n_tx", 0)

        for tx in data.get("txs", [])[:20]:
            ts = str(tx.get("time", ""))
            for inp in tx.get("inputs", []):
                from_addr = inp.get("prev_out", {}).get("addr", "")
                for out in tx.get("out", []):
                    to_addr = out.get("addr", "")
                    val_btc = out.get("value", 0) * satoshi_to_btc
                    label   = KNOWN_LABELS.get(to_addr, "")
                    report.transactions.append(Transaction(
                        hash=tx.get("hash", "")[:16],
                        from_addr=from_addr,
                        to_addr=to_addr,
                        value_usd=round(val_btc * btc_price, 2),
                        value_crypto=f"{val_btc:.8f} BTC",
                        timestamp=ts,
                        chain="Bitcoin",
                        label=label,
                    ))
                    if to_addr not in (address, "") and to_addr not in report.connected_wallets:
                        report.connected_wallets.append(to_addr)
                    if label:
                        report.risk_flags.append(f"Funds moved to {label} — KYC available")
                        report.is_exchange = True

    except Exception as exc:
        report.errors.append(f"Bitcoin trace: {exc}")


async def _trace_ethereum(client: httpx.AsyncClient, address: str, report: WalletReport) -> None:
    """Trace Ethereum/BSC wallet using Etherscan free API."""
    chains = [
        ("Ethereum", "https://api.etherscan.io/api", "ETH"),
        ("BNB Chain", "https://api.bscscan.com/api", "BNB"),
    ]
    for chain_name, base_url, symbol in chains:
        try:
            # Balance
            r = await client.get(base_url, params={
                "module": "account", "action": "balance",
                "address": address, "tag": "latest", "apikey": "YourApiKeyToken"
            }, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "1":
                    wei = int(data.get("result", "0"))
                    eth = wei / 1e18

                    # Get price
                    price_r = await client.get(
                        f"https://api.coingecko.com/api/v3/simple/price?ids={'ethereum' if symbol == 'ETH' else 'binancecoin'}&vs_currencies=usd",
                        timeout=8
                    )
                    price = 0.0
                    if price_r.status_code == 200:
                        pd = price_r.json()
                        price = list(pd.values())[0].get("usd", 0.0) if pd else 0.0

                    if chain_name == "Ethereum" or not report.balance_crypto:
                        report.balance_crypto = f"{eth:.6f} {symbol}"
                        report.balance_usd    = round(eth * price, 2)

            # Transactions
            r2 = await client.get(base_url, params={
                "module": "account", "action": "txlist",
                "address": address, "startblock": 0, "endblock": 99999999,
                "sort": "desc", "apikey": "YourApiKeyToken", "offset": 20, "page": 1
            }, timeout=12)
            if r2.status_code == 200:
                data2 = r2.json()
                txs = data2.get("result", []) if isinstance(data2.get("result"), list) else []
                if txs:
                    report.first_seen = txs[-1].get("timeStamp", "")
                    report.last_seen  = txs[0].get("timeStamp", "")
                    report.tx_count   = max(report.tx_count, len(txs))

                for tx in txs[:15]:
                    to_addr = tx.get("to", "")
                    label   = KNOWN_LABELS.get(to_addr.lower(), "")
                    val_eth = int(tx.get("value", "0")) / 1e18
                    report.transactions.append(Transaction(
                        hash=tx.get("hash", "")[:16],
                        from_addr=tx.get("from", ""),
                        to_addr=to_addr,
                        value_usd=round(val_eth * price, 2),
                        value_crypto=f"{val_eth:.6f} {symbol}",
                        timestamp=tx.get("timeStamp", ""),
                        chain=chain_name,
                        label=label,
                    ))
                    if to_addr and to_addr != address and to_addr not in report.connected_wallets:
                        report.connected_wallets.append(to_addr)
                    if label:
                        report.risk_flags.append(f"Funds sent to {label} — police KYC request possible")
                        report.is_exchange = True
        except Exception as exc:
            report.errors.append(f"{chain_name} trace: {exc}")


async def _trace_tron(client: httpx.AsyncClient, address: str, report: WalletReport) -> None:
    """Trace TRON/USDT-TRC20 wallet using Tronscan API (free)."""
    try:
        r = await client.get(
            f"https://apilist.tronscan.org/api/account",
            params={"address": address},
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json()
            trx_bal = data.get("balance", 0) / 1e6
            report.balance_crypto = f"{trx_bal:.4f} TRX"

            # USDT-TRC20 balance (most common scam token)
            for token in data.get("trc20token_balances", []):
                if token.get("tokenAbbr", "").upper() == "USDT":
                    usdt = float(token.get("balance", 0)) / 1e6
                    report.balance_usd    = round(usdt, 2)
                    report.balance_crypto += f" + {usdt:.2f} USDT"
                    if usdt > 100:
                        report.risk_flags.append(f"USDT-TRC20 balance: ${usdt:.2f} — scammer may be holding funds here")

            # Transactions
            r2 = await client.get(
                "https://apilist.tronscan.org/api/transaction",
                params={"address": address, "limit": 20, "sort": "-timestamp"},
                timeout=12,
            )
            if r2.status_code == 200:
                for tx in r2.json().get("data", [])[:15]:
                    report.transactions.append(Transaction(
                        hash=tx.get("hash", "")[:16],
                        from_addr=tx.get("ownerAddress", ""),
                        to_addr=tx.get("toAddress", ""),
                        value_usd=0.0,
                        value_crypto=f"{tx.get('contractData', {}).get('amount', 0) / 1e6:.4f} TRX",
                        timestamp=str(tx.get("timestamp", "")),
                        chain="TRON",
                    ))
    except Exception as exc:
        report.errors.append(f"TRON trace: {exc}")


def _compute_risk(report: WalletReport) -> tuple[int, list[str]]:
    score = 0
    flags = list(report.risk_flags)

    if report.total_received > 10000:
        score += 30
        flags.append(f"High total received: ${report.total_received:,.0f}")
    if report.balance_usd > 1000:
        score += 15
        flags.append(f"Active balance: ${report.balance_usd:,.0f}")
    if report.mixer_detected:
        score += 40
        flags.append("Mixer/tumbler detected — active money laundering")
    if report.is_exchange:
        score += 10
        flags.append("Funds traceable to KYC exchange — police can subpoena")
    if len(report.connected_wallets) > 10:
        score += 15
        flags.append(f"Complex network: {len(report.connected_wallets)} connected wallets")

    return min(100, score), list(set(flags))


async def trace_wallet(address: str) -> WalletReport:
    """Master function: auto-detect chain and trace the wallet."""
    address = address.strip()
    chain   = _detect_chain(address)
    report  = WalletReport(address=address, chain=chain)
    report.label = KNOWN_LABELS.get(address.lower(), "")

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        if chain == "Bitcoin":
            await _trace_bitcoin(client, address, report)
        elif chain in ("Ethereum", "Unknown"):
            await _trace_ethereum(client, address, report)
            if chain == "Unknown" and not report.tx_count:
                report.chain = "Unknown"
        elif chain == "TRON":
            await _trace_tron(client, address, report)

    # Check for mixer patterns in transaction destinations
    for tx in report.transactions:
        for pattern in MIXER_PATTERNS:
            if re.search(pattern, tx.to_addr, re.IGNORECASE):
                report.mixer_detected = True

    report.risk_score, report.risk_flags = _compute_risk(report)
    report.connected_wallets = report.connected_wallets[:20]  # cap
    report.analyzed_at = time.time()

    logger.info(
        "wallet_traced",
        address=address[:16],
        chain=chain,
        balance_usd=report.balance_usd,
        tx_count=report.tx_count,
        risk=report.risk_score,
    )
    return report
