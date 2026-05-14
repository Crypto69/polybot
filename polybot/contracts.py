"""Polymarket contract addresses on Polygon mainnet (chain 137).

Source: https://docs.polymarket.com/resources/contracts
"""
from __future__ import annotations

# Trading
CTF_EXCHANGE          = "0xE111180000d2663C0091e4f400237545B87B996B"
NEG_RISK_CTF_EXCHANGE = "0xe2222d279d744050d28e00520010520000310F59"
CONDITIONAL_TOKENS    = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
NEG_RISK_ADAPTER      = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

# Collateral tokens
PUSD   = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"  # what trades settle in
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # what you fund the wallet with
USDC   = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"  # native USDC (not used by Polymarket)

# Wrapping / unwrapping
COLLATERAL_ONRAMP  = "0x93070a847efEf7F70739046A929D47a521F5B8ee"  # USDC.e -> pUSD
COLLATERAL_OFFRAMP = "0x2957922Eb93258b93368531d39fAcCA3B4dC5854"  # pUSD -> USDC.e

# Common ABI fragments
ERC20_ABI = [
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "account", "type": "address"}],
     "outputs": [{"type": "uint256"}]},
    {"name": "decimals", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint8"}]},
    {"name": "symbol", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "string"}]},
    {"name": "allowance", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"}],
     "outputs": [{"type": "uint256"}]},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "spender", "type": "address"},
                {"name": "amount", "type": "uint256"}],
     "outputs": [{"type": "bool"}]},
    {"name": "transfer", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"}],
     "outputs": [{"type": "bool"}]},
]

ONRAMP_ABI = [
    {"name": "wrap", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "_asset",  "type": "address"},
                {"name": "_to",     "type": "address"},
                {"name": "_amount", "type": "uint256"}],
     "outputs": []},
]

OFFRAMP_ABI = [
    {"name": "unwrap", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "_asset",  "type": "address"},
                {"name": "_to",     "type": "address"},
                {"name": "_amount", "type": "uint256"}],
     "outputs": []},
]
