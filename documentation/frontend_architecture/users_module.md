# Users module

`src/module/users` contributes the `/users` page and its menu entry. The route requires `users:read`; creation and status actions are shown only with `users:manage`. The server enforces these permissions and refuses self status changes.

The User Management page uses `AppTable` with `POST /users/search` for server-side paging and sorting. The toolbar has one quick search across username, name, and email. A shared Advanced filters dialog lets administrators combine up to 20 username, name, email, account status, admin lock, created date, and last sign-in conditions. All conditions must match; filters are sent only when Apply filters is selected. Closing the dialog discards unapplied changes. The page shows enabled/disabled status and a separate lock badge. An administrator creates users with a unique username distinct from email and an optional set of role codes, or uses **Manage roles** in a user's row actions to replace an existing assignment. The assignment dialog loads current roles from `GET /users/{id}` and the paged role catalog from `GET /roles`, then saves through `PUT /users/{id}/roles`. The backend prevents changing your own roles and rejects roles granting permissions you do not hold.

Account state has two independent controls:

| Action | API | Effect |
| --- | --- | --- |
| Enable / disable | `PATCH /users/{id}` with `is_active` | Controls whether the account can sign in. |
| Lock / unlock | `PUT /users/{id}/lock` with `locked` | Persistent admin lock, separate from enabled status. Unlock also clears a failed-password lockout. |

Locking or disabling revokes refresh sessions. An access token already issued remains usable until its normal expiry. The list response includes `is_locked` and `locked_until` so the UI can show manual and temporary locks.
