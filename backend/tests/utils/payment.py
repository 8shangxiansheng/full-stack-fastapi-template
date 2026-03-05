import hmac
from hashlib import sha256
import time

from app.core.config import settings


def build_mockpay_callback_payload(
    *,
    out_trade_no: str,
    callback_status: str = "success",
    transaction_id: str | None = None,
    timestamp: int | None = None,
    secret: str | None = None,
) -> dict[str, str | int]:
    ts = timestamp or int(time.time())
    provider = "mockpay"
    tx_id = transaction_id or out_trade_no
    payload = (
        f'{{"out_trade_no":"{out_trade_no}","status":"{callback_status}"}}'
    )
    signing_secret = secret or settings.PAYMENT_CALLBACK_SIGNING_SECRET
    message = f"{provider}:{tx_id}:{ts}:{payload}"
    signature = hmac.new(
        signing_secret.encode(),
        message.encode(),
        sha256,
    ).hexdigest()
    return {
        "provider": provider,
        "transaction_id": tx_id,
        "timestamp": ts,
        "payload": payload,
        "signature": signature,
    }
