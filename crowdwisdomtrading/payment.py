"""x402 payment session: a requests.Session that pays any 402 it meets, like ai-hedge-fund's wallet.py.

The private key never leaves this process and is never logged; errors are re-raised as PaymentFailed
with the key stripped from the message.
"""
from __future__ import annotations

from typing import Any

import requests

BASE_MAINNET = "eip155:8453"
BASE_SEPOLIA = "eip155:84532"


class PaymentFailed(requests.RequestException):
    """The x402 payment could not be made (no funds, facilitator down, wrong network)."""


def _scrub(text: str, secret: str) -> str:
    if not secret:
        return text
    out = text.replace(secret, "<redacted>")
    bare = secret[2:] if secret.lower().startswith("0x") else secret
    return out.replace(bare, "<redacted>") if bare else out


def payment_session(
    wallet_key: str, network: str = BASE_MAINNET, *, timeout: float = 60.0, base_url: str | None = None
) -> requests.Session:
    """requests.Session that pays x402 402s. The paying adapter is mounted only on `base_url` (when given) and
    redirects are off, so a 3xx to a third-party 402 can never be paid by accident. Needs crowdwisdomtrading[x402]."""
    try:
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http.clients.requests import PaymentError, x402HTTPAdapter
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact import ExactEvmScheme
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError("x402 payments need: pip install 'crowdwisdomtrading[x402]'") from exc

    client = x402ClientSync()
    client.register(network, ExactEvmScheme(EthAccountSigner(Account.from_key(wallet_key))))

    class _Adapter(x402HTTPAdapter):
        def send(self, request: Any, **kwargs: Any) -> Any:  # type: ignore[override]
            try:
                return super().send(request, **kwargs)
            except PaymentError as exc:
                raise PaymentFailed(_scrub(str(exc), wallet_key)) from None
            except Exception as exc:
                raise PaymentFailed(f"{type(exc).__name__}: {_scrub(str(exc), wallet_key)}") from None

    session = requests.Session()
    adapter = _Adapter(client)
    if base_url:
        session.mount(base_url.rstrip("/"), adapter)
    else:
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    session.request = _with_defaults(session.request, timeout)  # type: ignore[method-assign]
    return session


def _with_defaults(request_fn: Any, timeout: float) -> Any:
    def wrapped(method: str, url: str, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", timeout)
        kwargs.setdefault("allow_redirects", False)
        return request_fn(method, url, **kwargs)

    return wrapped


def decode_receipt(response: requests.Response) -> dict[str, Any] | None:
    """The PAYMENT-RESPONSE receipt (tx hash, payer, network) or None when the call was not paid."""
    header = response.headers.get("PAYMENT-RESPONSE")
    if not header:
        return None
    try:
        from x402.http import decode_payment_response_header

        settled = decode_payment_response_header(header)
    except Exception:
        return None
    return {
        "success": settled.success,
        "transaction": settled.transaction,
        "network": settled.network,
        "payer": settled.payer,
        "amount": settled.amount,
    }
