# Roles module

`src/module/roles` contributes the `/roles` page and the Role Management menu item. The route requires `roles:read`; create, edit, permission changes, and delete require `roles:manage`. The API enforces those permissions and its grant rules.

The list uses `POST /roles/search` for paging, sorting, quick search across code, name, and description, and an Advanced filters dialog. Filters can combine role name, code, system/custom type, and created date conditions. Unapplied changes are discarded when the dialog closes.

Administrators can create a role, edit its name and description, and delete custom roles after a confirmation. A role code is permanent. New roles start with no permissions, so the page opens the permission editor after creation. The editor loads the catalog from `GET /permissions`, groups permissions by resource, and disables permissions the current administrator cannot grant. System role permissions can be viewed but not changed; system roles cannot be deleted.

Deleting a role removes it from assigned users. Permission and deletion changes take effect for those users when they receive a new access token.
