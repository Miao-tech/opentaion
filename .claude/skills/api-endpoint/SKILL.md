---
name: api-endpoint
description: Scaffold a FastAPI route with Pydantic models and test stub
argument-hint: <router-name> <HTTP-method>
allowed-tools:
  - Read
  - Glob
  - Write
---

# Skill: api-endpoint

Scaffold a new FastAPI route for the OpenTalon API.

## Arguments

`$ARGUMENTS` — two words: router name and HTTP method
  Example: `usage GET`, `keys POST`, `proxy POST`

## Procedure

1. **Read existing router structure**
   - Glob `api/src/opentaion_api/routers/*.py` to see existing routers
   - Read the router file that matches the first argument, if it exists
   - If it does not exist, read one existing router to understand the pattern

2. **Parse arguments**
   - Router name: first word of `$ARGUMENTS` (e.g., `usage`)
   - HTTP method: second word of `$ARGUMENTS` (e.g., `GET`)
   - Derive endpoint path: `/{router-name}` (e.g., `/usage`)

3. **Create or update the router file**
   Write or append to `api/src/opentaion_api/routers/{router_name}.py`:

   \```python
   # api/src/opentaion_api/routers/{router_name}.py
   from fastapi import APIRouter, Depends
   from pydantic import BaseModel
   from ..auth import get_current_user

   router = APIRouter(prefix="/{router_name}", tags=["{router_name}"])

   class {RouterName}Response(BaseModel):
       # TODO: define response fields
       pass

   @router.{method}("/")
   async def handle_{router_name}_{method_lower}(
       current_user = Depends(get_current_user),
   ) -> {RouterName}Response:
       """[Brief description of this endpoint]"""
       raise NotImplementedError("Endpoint not yet implemented")
\```

4. **Create the test stub**
   Write `api/tests/test_{router_name}.py`:

   \```python
   # api/tests/test_{router_name}.py
   from fastapi.testclient import TestClient
   from opentaion_api.main import app
   
   client = TestClient(app)
   
   def test_{router_name}_{method_lower}_exists():
       # This test verifies the route is registered, not implemented
       response = client.{method_lower}("/{router_name}/")
       # 401 means the route exists but requires auth — expected at this stage
       assert response.status_code in [200, 401, 422]
   \```

5. **Report**
   Tell the user:
   - What files were created or modified
   - The route that was scaffolded: `{METHOD} /{router_name}/`
   - Next steps: implement the handler, define the Pydantic models, run migrations if needed

## Notes
- `{RouterName}` is the CamelCase version of the router name
- `{method_lower}` is the HTTP method in lowercase (get, post, delete)
- Do NOT run the server, tests, or any Bash commands — the developer runs those
- If the router file already exists, add the new route without touching existing routes
