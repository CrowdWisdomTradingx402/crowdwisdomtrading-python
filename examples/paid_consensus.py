"""Paid call with x402 (USDC on Base, $0.10). Needs: pip install "crowdwisdomtrading[x402]" and
X402_WALLET_PRIVATE_KEY set to a wallet holding a few dollars of USDC on Base. Fund it with small amounts only."""
from crowdwisdomtrading import Client

c = Client()
print(c.consensus("NVDA"))
print("receipt:", c.last_receipt)
