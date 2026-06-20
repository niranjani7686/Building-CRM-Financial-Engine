import json
import base64
from typing import List, Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# Stub user data for simulation/testing if JWT is not fully verify-configured
# In a real environment, this is decoded from the JWT token.
# To make local manual/test calls easy, we allow decoding a base64-like JSON token or a mock bearer token.
# Format: Bearer {"user_id": "user123", "role": "admin", "client_id": null}
# Or simply a standard JWT token that we decode.
# For stub/development purposes, we will support standard token formats or a fallback mock.

def decode_jwt_token(token: str) -> dict:
    """
    Decodes the JWT token.
    TODO-INTEGRATION: Connect this to the shared auth server public key or secret validation.
    For now, it decodes a mock JSON token for development/testing,
    or falls back to a default mock user.
    """
    try:
        # Check if it looks like a JWT (three parts)
        parts = token.split(".")
        if len(parts) == 3:
            # Decode the payload part
            payload = parts[1]
            # Add padding if needed
            payload += "=" * ((4 - len(payload) % 4) % 4)
            decoded_bytes = base64.b64decode(payload)
            return json.loads(decoded_bytes.decode("utf-8"))
    except Exception:
        pass

    # Fallback/development mock check:
    # If the token is a JSON string, try to parse it
    try:
        return json.loads(token)
    except Exception:
        pass

    # Standard fallback mock user for local testing if the token is "mock-admin-token" or "mock-client-token"
    if token == "mock-admin-token":
        return {
            "user_id": "admin_user",
            "role": "admin",
            "client_id": None,
            "permissions": ["read", "write", "delete", "finance"]
        }
    elif token == "mock-employee-token":
        return {
            "user_id": "employee_user",
            "role": "employee",
            "client_id": None,
            "permissions": ["read", "write", "finance"]
        }
    elif token.startswith("mock-client-token-"):
        client_id = token.replace("mock-client-token-", "")
        return {
            "user_id": f"client_user_{client_id}",
            "role": "client",
            "client_id": client_id,
            "permissions": ["read"]
        }

    # Raise exception if token is invalid and no mock is detected
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """FastAPI dependency to extract and validate the JWT token from the Authorization header."""
    token = credentials.credentials
    user = decode_jwt_token(token)
    return user

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: dict = Security(get_current_user)) -> dict:
        user_role = user.get("role")
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not authorized to perform this action. Required: {self.allowed_roles}",
            )
        return user

def verify_client_access(user: dict, target_client_id: str):
    """
    Validates if the current user has access to the specified client_id.
    - Admins and Employees can access any client.
    - Client users can ONLY access their own client_id.
    """
    user_role = user.get("role")
    if user_role in ["admin", "employee"]:
        return True
    
    user_client_id = user.get("client_id")
    if user_role == "client" and user_client_id == target_client_id:
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. You are not authorized to access this client's records.",
    )
