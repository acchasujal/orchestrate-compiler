# Final Knowledge Integration Audit

## Verification status

- Output coverage: 110/110.
- Output schema and evidence ownership: passed.
- Regression suite: passed, 11 named checks.
- Unit tests: passed, 51 tests.
- Provider calls during final deterministic run: 0.
- Fixed media knowledge reused locally; no new Gemini perception was required.

The submission audit still reports `.env` and `__pycache__` artifacts. They must be excluded from `code.zip`; they were not deleted because they are environment/user artifacts.

## Confirmed changes

| Messages | Deterministic change | Why stronger |
|---|---|---|
| `msg_015`, `msg_016`, `msg_044`, `msg_046`, `msg_070`, `msg_072`, `msg_073`, `msg_079`, `msg_091`, `msg_095`, `msg_107` | OTP/login-code/account-blocking requests → `mute/scam` | Credential requests are terminal safety signals, including mixed-language forms and router-injection wrappers. |
| `msg_017`, `msg_022`, `msg_054`, `msg_059`, `msg_064`, `msg_074` | Payment pressure, QR/link, wallet-detail, fee, account-number, and land-token requests → `mute/scam` | The content requests money or sensitive financial information under time pressure. |
| `msg_021`, `msg_067` | Trusted administrative payment messages → `notify/payment` | Explicit anti-link language and admin context distinguish them from payment scams. |
| `msg_003`, `msg_004`, `msg_023`, `msg_025`, `msg_075`, `msg_093` | Verified transactional business messages → `notify/business_update` | Reports and promotional preferences are advisory for transactions, not scam labels. |
| `msg_049` | Same-day return pickup → `notify/business_update` | A delivery/pickup window is operationally time-sensitive. |
| `msg_062` | Conflicting fire-alarm text plus missing-person poster → `notify/urgent` | Safety-relevant media is no longer discarded when text is present. |
| `msg_081` | Cached airport voice update → `notify/event` | Cached ASR identifies a changed pickup time. |
| `msg_082`, `msg_086` | Cached bank/OTP voice content → `mute/scam` | Cached voice semantics are consumed without retranscription. |
| `msg_104`, `msg_045`, `msg_055`, `msg_080` | Explicit deadlines/time windows → `notify/urgent` | Time expressions such as “by 6 PM” and “next 10 minutes” are now recognized. |
| `msg_032`, `msg_053`, `msg_068`, `msg_071`, `msg_090`, `msg_097`, `msg_099` | Explicitly non-urgent content → digest | “No rush,” “nothing urgent,” and equivalent language suppress unnecessary interruption. |

Some rows changed only in `message_type` because the prior action was already reasonable; those changes are category corrections, not label claims about hidden ground truth.

## Deliberately not encoded

- Exact hidden labels for every message.
- Unknown voice-note semantics without verified ASR.
- Treating every business report as scam.
- Treating every same-day business message as notify.
- Treating every promotion as mute.

The fixed knowledge files contain semantic facts and audit notes only; they do not contain output labels.
