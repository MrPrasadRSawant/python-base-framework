# Developer module

`src/module/developer` contributes the developer monitoring and access screens. Each route and menu entry uses the matching backend permission; the API remains the authority for access.

| Screen | Route | Permission | Data source |
|---|---|---|---|
| Exception Analysis | `/developer/exceptions` | `exception_logs:read` | `POST /exception-logs/search`, `GET /exception-logs/{id}` |
| Request Lifecycle | `/developer/requests` | `request_logs:read` | `POST /requests/report` |
| Request trace drawer | `/developer/requests?requestId={requestId}` | `request_logs:read` | `GET /requests/{requestId}/report`, optionally `GET /exception-logs/{id}` |
| Permission Management | `/developer/permissions` | `roles:read`; edits also require `roles:manage` | `/roles`, `/permissions`, `/roles/{id}`, `PUT /roles/{id}/permissions` |

Exception metrics and error-code frequency describe the latest result page returned by the API. The exception detail dialog shows the redacted traceback and links to the corresponding request when request-log access is present.

Request Lifecycle summarizes the latest request report page. Selecting a row opens a wide right-side trace drawer while preserving the table position and filters. The drawer shows the received time, response status, total duration, nested service calls, and failure context. A service's total duration includes child calls; its own time excludes them. Request and service-call logs are written asynchronously, so the newest request may take about one second to appear. The `requestId` query parameter can open a specific trace directly.

The permission catalog is defined by the backend and changes with application releases. Permission Management assigns catalog entries to custom roles. System roles are read-only. A caller can grant or remove only permissions they hold; the Developer role has log read access plus `roles:read` and `roles:manage` to administer assignments within that scope. It does not have `users:manage`, so it cannot assign roles to user accounts.
