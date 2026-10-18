# Resolver Test Plan

The resolver receives one normalized message row and loader-owned indexed tables. It returns one `ResolvedContext` or raises a typed `ContextResolutionError`. It must never scan raw tables, retrieve history, calculate personalization, inspect media, or call providers.

## Common test contract

All successful cases must verify:

- `message_id`, `user_id`, `conversation_type`, and `created_at` are preserved.
- The recipient record is resolved from `users`.
- The sender record is resolved when `sender_user_id` is present.
- Optional absent relationships remain `None`.
- No output contains copied historical or notification-summary rows.

## Test cases

| ID | Conversation | Purpose | Input | Expected output | Expected exception |
|---|---|---|---|---|---|
| R-01 | personal | Resolve the minimal personal context | A real personal row with a sender | Recipient and sender records populated; group, membership, business, and business history are `None` | None |
| R-02 | personal | Preserve message timestamp | R-01 message | `created_at` equals the parsed source timestamp exactly | None |
| R-03 | personal | Reject missing required recipient | R-01 with unknown `user_id` | No context returned | `ContextResolutionError` |
| R-04 | personal | Reject missing required sender | R-01 with `sender_user_id=None` | No context returned | `ContextResolutionError` |
| R-05 | personal | Reject corrupted sender foreign key | R-01 with unknown `sender_user_id` | No context returned | `ContextResolutionError` |
| R-06 | personal | Reject invalid conversation type | R-01 with `conversation_type="unknown"` | No context returned | `ContextResolutionError` |
| R-07 | group | Resolve group context | A real group row | Recipient, sender, group, and recipient membership populated | None |
| R-08 | group | Validate group membership | R-07 with a valid group and recipient pair absent from `group_members` | No context returned | `ContextResolutionError` |
| R-09 | group | Reject missing group foreign key | R-07 with unknown `group_id` | No context returned | `ContextResolutionError` |
| R-10 | group | Reject nullable sender in a group | R-07 with `sender_user_id=None` | No context returned | `ContextResolutionError` |
| R-11 | group | Reject corrupted sender foreign key | R-07 with unknown `sender_user_id` | No context returned | `ContextResolutionError` |
| R-12 | business | Resolve business context | A real business row with a business account | Recipient and business record populated; sender/group/membership are `None` | None |
| R-13 | business | Resolve optional business history when present | A business row whose `(user_id, business_id)` exists in `user_business_history` | `user_business_history` populated | None |
| R-14 | business | Preserve missing optional business history | A business row whose pair is absent from `user_business_history` | `user_business_history is None` | None |
| R-15 | business | Reject missing business foreign key | R-12 with unknown `business_id` | No context returned | `ContextResolutionError` |
| R-16 | business | Allow nullable business sender | R-12 with `sender_user_id=None` | `sender is None`; context remains valid | None |
| R-17 | business | Reject invalid group combination | R-12 with a non-null `group_id` | No context returned | `ContextResolutionError` |
| R-18 | business | Reject invalid sender if supplied | R-12 with unknown non-null `sender_user_id` | No context returned | `ContextResolutionError` |
| R-19 | all | Preserve source order | Iterate the 110 source rows in order and resolve each | Output message IDs equal the source sequence exactly | None |
| R-20 | all | Reject missing message ID | Any valid row with `message_id=None` | No context returned | `ContextResolutionError` |
| R-21 | all | Reject malformed timestamp | Any valid row with an invalid `created_at` | No context returned | `ContextResolutionError` |
| R-22 | all | Ensure resolver is index-only | Resolve every target row using `DatasetTables` mappings | All rows resolve without raw-table traversal or downstream access | None |

## Acceptance criteria

- Every listed case is executable.
- All 110 target rows resolve successfully.
- Required relationships fail closed with `ContextResolutionError`.
- Optional relationships remain explicit `None`.
- No test imports retrieval, personalization, perception, provider, or output modules.
