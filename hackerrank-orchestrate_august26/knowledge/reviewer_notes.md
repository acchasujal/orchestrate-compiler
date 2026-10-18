# Final knowledge integration notes

Confirmed from source code, participant data, cached perception, and direct media inspection:

- Business report counts were used as hard scam evidence even for verified, relationship-backed transactional messages.
- Promotional opt-out was not scoped to promotions.
- OTP, wallet-PIN, account-blocking, QR/payment-fee, and account-number requests bypassed safety in multiple rows.
- Text content replaced media content instead of being reconciled with it; `msg_062` pairs fire-alarm text with a missing-person poster.
- Sender trust, dismissal signals, and message category signals were computed but underused.
- Confidence was gate-fixed and degraded perception was not disclosed in row reasons.
- Cached media interpretations above are fixed-dataset facts and must be reused without another provider call.

Unsupported or not strong enough to encode as rules:

- Exact hidden labels for every row.
- Treating every business report as scam.
- Treating every same-day business message as notify.
- Treating every unknown voice note as mute.
