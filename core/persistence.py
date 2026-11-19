"""Central database boundary. All writing records are owner scoped."""
class OwnershipError(PermissionError):
    pass

def require_owner_id(user_id):
    value = str(user_id or "").strip()
    if not value:
        raise OwnershipError("Authenticated owner ID is required")
    return value

class ScopedPersistence:
    def __init__(self, supabase_client, user_id):
        self.client = supabase_client
        self.user_id = require_owner_id(user_id)

    def get_project(self, project_id):
        return (self.client.table("writersblock_projects")
                .select("*").eq("id", str(project_id))
                .eq("user_id", self.user_id).limit(1).execute())

    def get_project_session(self, session_id, project_id):
        return (self.client.table("writersblock_project_drafts")
                .select("*").eq("id", str(session_id))
                .eq("project_id", str(project_id))
                .eq("user_id", self.user_id)
                .eq("draft_type", "project_session").limit(1).execute())

    def delete_manuscript_version(self, version_id, project_id):
        return (self.client.table("writersblock_manuscript_versions")
                .delete().eq("id", str(version_id))
                .eq("project_id", str(project_id))
                .eq("user_id", self.user_id).execute())


class OwnedClient:
    """Scope every writing query, including historical inline call chains.

    The application supplies an Auth-backed authorization callback. Explicit
    owner-only construction remains for isolated offline fixtures. Profiles are
    read-only and owner scoped; database RLS independently enforces ownership.
    """
    TABLES = {"writersblock_projects", "writersblock_project_drafts",
              "writersblock_manuscript_versions"}

    def __init__(self, client, owner_provider, observer=None, authorize=None, checkpoint_state=None):
        self._client = client
        self._owner_provider = owner_provider
        self._observer = observer
        self._authorize = authorize
        self._checkpoint_state = checkpoint_state

    def _checked_owner(self):
        if self._authorize is not None:
            verified = require_owner_id(self._authorize())
            if verified != require_owner_id(self._owner_provider()):
                raise OwnershipError("Authenticated account binding changed")
        return require_owner_id(self._owner_provider())

    def table(self, name):
        if name not in self.TABLES | {"writersblock_users"}:
            raise OwnershipError("Unapproved database table")
        return OwnedQuery(self, name, self._checked_owner())

    def save_project_checkpoint(self, project_id, row_id, expected_content, new_content):
        """POST the exact expected text; avoid large manuscript filters in URLs."""
        owner = self._checked_owner()
        result = self._client.rpc('wbs_save_project_checkpoint', {
            'target_project': str(project_id), 'target_revision': str(row_id),
            'expected_owner': owner, 'expected_content': expected_content,
            'new_content': new_content,
        }).execute()
        if not getattr(result, 'data', None):
            from core.save_conflicts import SaveConflictError
            raise SaveConflictError('Another session saved this revision. Reload before saving; your unsaved work is preserved.')
        if self._observer is not None:
            self._observer('writersblock_project_drafts', 'update', result.data, owner)
        if self._checkpoint_state is not None:
            from core.save_conflicts import remember_checkpoint
            remember_checkpoint(self._checkpoint_state, project_id, result.data[0])
        return result


class OwnedQuery:
    def __init__(self, boundary, table, owner):
        self.boundary, self.table_name, self.owner = boundary, table, owner
        self.steps = []
        self.operation = None
        self.payload = None

    def __getattr__(self, name):
        if name.startswith("_") or name in {"rpc", "upsert"}:
            raise OwnershipError("Unsupported scoped database operation")
        def chained(*args, **kwargs):
            if self.table_name == "writersblock_users" and name in {"insert", "update", "delete"}:
                raise OwnershipError("Account and license fields are not client writable")
            if name in {"insert", "update"}:
                from copy import deepcopy
                payload = deepcopy(args[0])
                rows = payload if isinstance(payload, list) else [payload]
                for row in rows:
                    if require_owner_id(row.get("user_id", self.owner)) != self.owner:
                        raise OwnershipError("Cannot write another owner's record")
                    if name == "insert":
                        row["user_id"] = self.owner
                self.payload = rows
                args = (payload,) + args[1:]
            if name in {"select", "insert", "update", "delete"}:
                if self.operation is None or name != "select":
                    self.operation = name
            self.steps.append((name,args,kwargs))
            return self
        return chained

    def execute(self):
        if self.boundary._checked_owner() != self.owner:
            raise OwnershipError("Owner changed during query")
        # Existing format helpers remain unchanged. Their exact-row checkpoint
        # updates use the same atomic boundary as the shared Save Project path.
        if (self.table_name == 'writersblock_project_drafts' and self.operation == 'update'
                and self.boundary._checkpoint_state is not None and self.payload
                and 'draft_content' in self.payload[0]):
            filters={args[0]:args[1] for name,args,kw in self.steps if name=='eq' and len(args)==2}
            if filters.get('draft_type') == 'project_session':
                from core.save_conflicts import expected_checkpoint
                project_id,revision_id=filters.get('project_id'),filters.get('id')
                if not project_id or not revision_id:
                    raise OwnershipError('Checkpoint updates require exact project and revision IDs')
                expected=expected_checkpoint(self.boundary._checkpoint_state,project_id,revision_id)
                return self.boundary.save_project_checkpoint(project_id,revision_id,expected,self.payload[0]['draft_content'])
        # Reject child records pointing at another user's project before writing.
        if self.table_name in {"writersblock_project_drafts", "writersblock_manuscript_versions"}:
            for row in self.payload or []:
                project_id = row.get("project_id")
                if project_id:
                    result = (self.boundary._client.table("writersblock_projects")
                              .select("id").eq("id", project_id)
                              .eq("user_id", self.owner).limit(1).execute())
                    if not result.data:
                        raise OwnershipError("Project does not belong to current owner")
        query = self.boundary._client.table(self.table_name)
        for name,args,kwargs in self.steps:
            query = getattr(query,name)(*args,**kwargs)
        if self.operation != "insert":
            query = query.eq("id" if self.table_name == "writersblock_users" else "user_id", self.owner)
        result = query.execute()
        if self.boundary._observer is not None:
            self.boundary._observer(self.table_name, self.operation, getattr(result, "data", None) or [], self.owner)
        return result
