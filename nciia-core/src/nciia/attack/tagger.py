"""
MITRE ATT&CK Auto-Tagger — N-CIIA

Auto-maps signals, signals content, and personas to MITRE ATT&CK
techniques using keyword matching + semantic patterns.
Outputs navigator-compatible layer JSON.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from nciia.utils import get_logger

logger = get_logger(__name__)


# ─── Embedded ATT&CK technique index ─────────────────────────────────────────
# Format: (technique_id, name, tactic, keywords)

ATTACK_TECHNIQUES: list[tuple[str, str, str, list[str]]] = [
    # Reconnaissance
    ("T1595", "Active Scanning",            "Reconnaissance",       ["port scan", "nmap", "masscan", "shodan", "scanning", "banner grab"]),
    ("T1592", "Gather Victim Host Info",    "Reconnaissance",       ["fingerprint", "os detection", "service version", "whois", "rdap"]),
    ("T1589", "Gather Victim Identity Info","Reconnaissance",       ["email harvesting", "linkedin", "username enumeration", "email lookup", "hibp"]),
    ("T1593", "Search Open Websites",       "Reconnaissance",       ["google dork", "github leak", "pastebin", "shodan dork", "censys"]),
    ("T1596", "Search Open Tech Databases", "Reconnaissance",       ["crt.sh", "certificate transparency", "bgp", "asn lookup", "passive dns"]),
    # Resource Development
    ("T1583", "Acquire Infrastructure",     "Resource Development", ["vps", "bulletproof host", "domain registration", "newly registered", "c2 server"]),
    ("T1584", "Compromise Infrastructure",  "Resource Development", ["compromised server", "hijacked domain", "hacked hosting"]),
    ("T1587", "Develop Capabilities",       "Resource Development", ["malware development", "exploit kit", "custom tool", "rat", "implant"]),
    ("T1588", "Obtain Capabilities",        "Resource Development", ["dark web market", "exploit purchase", "malware as a service", "maas", "raas"]),
    # Initial Access
    ("T1190", "Exploit Public-Facing App",  "Initial Access",       ["cve-", "exploit", "rce", "sqli", "sql injection", "xss", "vulnerability", "0day", "zero-day"]),
    ("T1566", "Phishing",                   "Initial Access",       ["phishing", "spear phish", "credential harvest", "fake login", "clone site"]),
    ("T1133", "External Remote Services",   "Initial Access",       ["vpn", "rdp", "ssh", "citrix", "remote desktop", "teamviewer"]),
    ("T1199", "Trusted Relationship",       "Initial Access",       ["supply chain", "third party", "vendor access", "msp"]),
    ("T1078", "Valid Accounts",             "Initial Access",       ["credential stuffing", "password spray", "stolen credentials", "account takeover"]),
    # Execution
    ("T1059", "Command and Scripting",      "Execution",            ["powershell", "bash", "python script", "vba macro", "javascript", "cmd.exe", "wscript"]),
    ("T1204", "User Execution",             "Execution",            ["malicious attachment", "macro enabled", "double-click", "user opened"]),
    ("T1203", "Exploitation for Execution", "Execution",            ["use-after-free", "heap spray", "buffer overflow", "jit spray"]),
    # Persistence
    ("T1053", "Scheduled Task/Job",         "Persistence",          ["cron job", "scheduled task", "at command", "launchd", "systemd"]),
    ("T1547", "Boot/Logon Autostart",       "Persistence",          ["registry run", "startup folder", "autorun", "rc.local", "init.d"]),
    ("T1098", "Account Manipulation",       "Persistence",          ["add admin", "new user", "backdoor account", "ssh key added"]),
    # Defense Evasion
    ("T1027", "Obfuscated Files",           "Defense Evasion",      ["base64 encoded", "xor encoded", "packed", "obfuscated", "encrypted payload"]),
    ("T1036", "Masquerading",               "Defense Evasion",      ["renamed binary", "fake process", "disguised", "svchost", "typosquatting"]),
    ("T1562", "Impair Defenses",            "Defense Evasion",      ["disable antivirus", "disable firewall", "kill process", "tamper protection"]),
    ("T1070", "Indicator Removal",          "Defense Evasion",      ["log deletion", "clear event log", "wipe logs", "timestomping", "shred"]),
    # Credential Access
    ("T1110", "Brute Force",                "Credential Access",    ["brute force", "password spray", "credential stuffing", "hydra", "medusa", "hashcat"]),
    ("T1003", "OS Credential Dumping",      "Credential Access",    ["mimikatz", "lsass dump", "hashdump", "ntds.dit", "sam database", "sekurlsa"]),
    ("T1056", "Input Capture",              "Credential Access",    ["keylogger", "form grab", "keystroke", "credential intercept"]),
    ("T1528", "Steal App Access Token",     "Credential Access",    ["oauth token", "api key stolen", "jwt stolen", "cookie theft", "bearer token"]),
    # Discovery
    ("T1082", "System Information",         "Discovery",            ["systeminfo", "uname", "os version", "hostname", "whoami", "ipconfig"]),
    ("T1083", "File/Directory Discovery",   "Discovery",            ["dir listing", "ls -la", "find .", "tree", "file enumeration"]),
    ("T1046", "Network Service Discovery",  "Discovery",            ["port scan", "service scan", "nmap", "netstat", "open ports"]),
    ("T1018", "Remote System Discovery",    "Discovery",            ["arp scan", "ping sweep", "nbtscan", "net view", "ldap query"]),
    # Lateral Movement
    ("T1021", "Remote Services",            "Lateral Movement",     ["psexec", "wmiexec", "ssh lateral", "rdp lateral", "smb pass-the-hash"]),
    ("T1563", "Remote Service Session",     "Lateral Movement",     ["session hijack", "rdp hijack", "token impersonation"]),
    ("T1534", "Internal Spearphishing",     "Lateral Movement",     ["internal phishing", "lateral email", "compromised account email"]),
    # Collection
    ("T1119", "Automated Collection",       "Collection",           ["automated scrape", "bulk collect", "data mining", "crawler", "spider"]),
    ("T1039", "Data from Network Share",    "Collection",           ["smb share", "nfs mount", "network drive", "fileshare"]),
    ("T1113", "Screen Capture",             "Collection",           ["screenshot", "screengrab", "vnc capture"]),
    ("T1114", "Email Collection",           "Collection",           ["email exfil", "inbox dump", "imap access", "owa access"]),
    # Command and Control
    ("T1071", "App Layer Protocol",         "Command and Control",  ["c2", "c&c", "command control", "http beacon", "dns tunnel", "http callback"]),
    ("T1095", "Non-App Layer Protocol",     "Command and Control",  ["raw socket", "icmp tunnel", "tcp beacon", "udp c2"]),
    ("T1090", "Proxy",                      "Command and Control",  ["tor proxy", "socks proxy", "vpn tunnel", "cdn fronting", "domain fronting"]),
    ("T1105", "Ingress Tool Transfer",      "Command and Control",  ["wget", "curl download", "powershell download", "bitsadmin", "certutil"]),
    ("T1572", "Protocol Tunneling",         "Command and Control",  ["dns tunneling", "icmp tunnel", "http tunnel", "iodine", "dnscat"]),
    # Exfiltration
    ("T1041", "Exfil Over C2",              "Exfiltration",         ["data exfil", "send to c2", "upload to attacker", "phone home"]),
    ("T1048", "Exfil Over Alt Protocol",    "Exfiltration",         ["dns exfil", "ftp exfil", "smtp exfil", "icmp exfil"]),
    ("T1567", "Exfil to Cloud",             "Exfiltration",         ["upload to s3", "dropbox upload", "google drive upload", "pastebin upload", "github push"]),
    # Impact
    ("T1486", "Data Encrypted (Ransom)",    "Impact",               ["ransomware", "encrypt files", "ransom note", "bitcoin demand", "decrypt key"]),
    ("T1485", "Data Destruction",           "Impact",               ["wiper", "disk wipe", "delete files", "shred data", "overwrite disk"]),
    ("T1498", "Network DoS",                "Impact",               ["ddos", "dos attack", "flood", "amplification", "botnet attack"]),
    ("T1499", "Endpoint DoS",               "Impact",               ["resource exhaustion", "fork bomb", "cpu spike", "memory leak"]),
    ("T1491", "Defacement",                 "Impact",               ["website defaced", "page replaced", "graffiti", "deface"]),
]

# Build a fast lookup: keyword → list of technique IDs
_KW_INDEX: dict[str, list[str]] = {}
_TECHNIQUE_MAP: dict[str, dict] = {}

for tid, name, tactic, keywords in ATTACK_TECHNIQUES:
    _TECHNIQUE_MAP[tid] = {"id": tid, "name": name, "tactic": tactic}
    for kw in keywords:
        _KW_INDEX.setdefault(kw.lower(), []).append(tid)


# ─── Tagger ───────────────────────────────────────────────────────────────────

@dataclass
class TechniqueMatch:
    technique_id: str
    name: str
    tactic: str
    matched_keywords: list[str]
    confidence: float


def tag_text(text: str, min_confidence: float = 0.1) -> list[TechniqueMatch]:
    """
    Match a text blob against all ATT&CK techniques.
    Returns sorted list of matches with confidence scores.
    """
    text_lower = text.lower()
    hit_counts: dict[str, list[str]] = {}

    for kw, tids in _KW_INDEX.items():
        if kw in text_lower:
            for tid in tids:
                hit_counts.setdefault(tid, []).append(kw)

    results: list[TechniqueMatch] = []
    for tid, kws in hit_counts.items():
        tech = _TECHNIQUE_MAP[tid]
        # Confidence = keyword hits / total keywords for that technique, capped at 1.0
        total_kws = len([k for _, _, _, keywords in ATTACK_TECHNIQUES
                         if _ == tid for k in keywords])
        confidence = min(len(set(kws)) / max(total_kws, 1), 1.0)

        if confidence >= min_confidence:
            results.append(TechniqueMatch(
                technique_id=tid,
                name=tech["name"],
                tactic=tech["tactic"],
                matched_keywords=list(set(kws)),
                confidence=round(confidence, 3),
            ))

    results.sort(key=lambda r: r.confidence, reverse=True)
    return results


def tag_signal(signal: dict[str, Any]) -> list[dict[str, Any]]:
    """Tag a signal dict. Returns serialisable list."""
    text_parts = [
        signal.get("raw_content", ""),
        signal.get("extracted_text", ""),
        signal.get("source_name", ""),
        str(signal.get("metadata", {})),
    ]
    full_text = " ".join(filter(None, text_parts))
    matches = tag_text(full_text)
    return [
        {
            "technique_id": m.technique_id,
            "name": m.name,
            "tactic": m.tactic,
            "matched_keywords": m.matched_keywords[:5],
            "confidence": m.confidence,
        }
        for m in matches[:10]  # top 10 per signal
    ]


def generate_navigator_layer(
    tagged_signals: list[list[dict[str, Any]]],
    layer_name: str = "N-CIIA Detected Techniques",
) -> dict[str, Any]:
    """
    Generate an ATT&CK Navigator layer JSON from a collection of tagged signals.
    Import at https://mitre-attack.github.io/attack-navigator/
    """
    from collections import Counter
    all_techniques: list[str] = []
    for tags in tagged_signals:
        for tag in tags:
            all_techniques.append(tag["technique_id"])

    counts = Counter(all_techniques)
    max_count = max(counts.values()) if counts else 1

    techniques_layer = []
    for tid, count in counts.items():
        score = int((count / max_count) * 100)
        techniques_layer.append({
            "techniqueID": tid,
            "score": score,
            "color": "",
            "comment": f"Detected {count} time(s)",
            "enabled": True,
            "metadata": [],
            "links": [],
            "showSubtechniques": False,
        })

    return {
        "name": layer_name,
        "versions": {"attack": "14", "navigator": "4.9.1", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": "Auto-generated by N-CIIA",
        "filters": {"platforms": ["Windows", "Linux", "macOS", "Network", "Cloud"]},
        "sorting": 3,
        "layout": {"layout": "side", "aggregateFunction": "average"},
        "hideDisabled": False,
        "techniques": techniques_layer,
        "gradient": {
            "colors": ["#ffffff", "#ff6666"],
            "minValue": 0,
            "maxValue": 100,
        },
    }


def get_tactic_summary(tagged_signals: list[list[dict[str, Any]]]) -> dict[str, int]:
    """Count technique hits per ATT&CK tactic."""
    from collections import Counter
    tactic_counts: Counter = Counter()
    seen: set[str] = set()
    for tags in tagged_signals:
        for tag in tags:
            key = f"{tag['tactic']}:{tag['technique_id']}"
            if key not in seen:
                tactic_counts[tag["tactic"]] += 1
                seen.add(key)
    return dict(tactic_counts)
