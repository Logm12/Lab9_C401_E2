"""
mcp_server.py — HTTP MCP Server (FastAPI) + In-Process Fallback
TIP-010: Final Polish — HTTP REST interface for MCP tools with pure OpenAI backends.

Architecture:
    - In-process: dispatch_tool() / list_tools() — used by policy_tool in fallback mode
    - HTTP server: FastAPI on port 8000 — used when server is running

Tools:
    1. search_kb(query, top_k)              → semantic search in ChromaDB
    2. get_ticket_info(ticket_id)           → mock Jira ticket lookup
    3. check_access_permission(level, role) → access control SOP check
    4. create_ticket(priority, title, desc) → create mock ticket
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load .env file (TIP-010)
load_dotenv()

# ─────────────────────────────────────────────
# Tool Definitions (Schema Discovery)
# ─────────────────────────────────────────────

TOOL_SCHEMAS = {
    "search_kb": {
        "name": "search_kb",
        "description": "Tim kiem Knowledge Base noi bo bang semantic search. Tra ve top-k chunks lien quan nhat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Cau hoi hoac keyword can tim"},
                "top_k": {"type": "integer", "description": "So chunks can tra ve", "default": 3},
            },
            "required": ["query"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "chunks": {"type": "array"},
                "sources": {"type": "array"},
                "total_found": {"type": "integer"},
            },
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Tra cuu thong tin ticket tu he thong Jira noi bo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "ID ticket (VD: IT-1234, P1-LATEST)"},
            },
            "required": ["ticket_id"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "priority": {"type": "string"},
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "created_at": {"type": "string"},
                "sla_deadline": {"type": "string"},
            },
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Kiem tra dieu kien cap quyen truy cap theo Access Control SOP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer", "description": "Level can cap (1, 2, hoac 3)"},
                "requester_role": {"type": "string", "description": "Vai tro cua nguoi yeu cau"},
                "is_emergency": {"type": "boolean", "description": "Co phai khan cap khong", "default": False},
            },
            "required": ["access_level", "requester_role"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "can_grant": {"type": "boolean"},
                "required_approvers": {"type": "array"},
                "emergency_override": {"type": "boolean"},
                "source": {"type": "string"},
            },
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Tao ticket moi trong he thong Jira (MOCK — khong tao that trong lab).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["priority", "title"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "url": {"type": "string"},
                "created_at": {"type": "string"},
            },
        },
    },
}

# ─────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────

def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """Semantic search in ChromaDB via retrieval worker."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from workers.retrieval import retrieve_dense
        chunks = retrieve_dense(query, top_k=top_k)
        sources = list({c["source"] for c in chunks})
        return {
            "chunks": chunks,
            "sources": sources,
            "total_found": len(chunks),
        }
    except Exception as e:
        return {
            "chunks": [{"text": f"[MOCK] ChromaDB unavailable (using random fallback): {e}", "source": "mock_data", "score": 0.5}],
            "sources": ["mock_data"],
            "total_found": 1,
        }

MOCK_TICKETS = {
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "title": "API Gateway down — toan bo nguoi dung khong dang nhap duoc",
        "status": "in_progress",
        "assignee": "nguyen.van.a@company.internal",
        "created_at": "2026-04-13T22:47:00",
        "sla_deadline": "2026-04-14T02:47:00",
        "escalated": True,
        "escalated_to": "senior_engineer_team",
        "notifications_sent": ["slack:#incident-p1", "email:incident@company.internal", "pagerduty:oncall"],
    },
    "IT-1234": {
        "ticket_id": "IT-1234",
        "priority": "P2",
        "title": "Feature login cham cho mot so user",
        "status": "open",
        "assignee": None,
        "created_at": "2026-04-13T09:15:00",
        "sla_deadline": "2026-04-14T09:15:00",
        "escalated": False,
    },
}

def tool_get_ticket_info(ticket_id: str) -> dict:
    """Mock Jira ticket lookup."""
    ticket = MOCK_TICKETS.get(ticket_id.upper())
    if ticket:
        return ticket
    return {
        "error": f"Ticket '{ticket_id}' khong tim thay trong he thong.",
        "available_mock_ids": list(MOCK_TICKETS.keys()),
    }

ACCESS_RULES = {
    1: {
        "required_approvers": ["Line Manager"],
        "emergency_can_bypass": False,
        "note": "Standard user access",
    },
    2: {
        "required_approvers": ["Line Manager", "IT Admin"],
        "emergency_can_bypass": True,
        "emergency_bypass_note": "Level 2 co the cap tam thoi voi approval cua Line Manager va IT Admin on-call.",
        "note": "Elevated access",
    },
    3: {
        "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "emergency_can_bypass": False,
        "note": "Admin access — khong co emergency bypass",
    },
}

def tool_check_access_permission(access_level: int, requester_role: str, is_emergency: bool = False) -> dict:
    """Access control check per SOP."""
    rule = ACCESS_RULES.get(access_level)
    if not rule:
        return {"error": f"Access level {access_level} khong hop le. Levels: 1, 2, 3."}

    notes = []
    if is_emergency and rule.get("emergency_can_bypass"):
        notes.append(rule.get("emergency_bypass_note", ""))
        can_grant = True
    elif is_emergency and not rule.get("emergency_can_bypass"):
        notes.append(f"Level {access_level} KHONG co emergency bypass. Phai follow quy trinh chuan.")
        can_grant = False
    else:
        can_grant = True

    return {
        "access_level": access_level,
        "can_grant": can_grant,
        "required_approvers": rule["required_approvers"],
        "approver_count": len(rule["required_approvers"]),
        "emergency_override": is_emergency and rule.get("emergency_can_bypass", False),
        "notes": notes,
        "source": "access_control_sop.txt",
    }

def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    """Create mock ticket."""
    mock_id = f"IT-{9900 + abs(hash(title)) % 99}"
    ticket = {
        "ticket_id": mock_id,
        "priority": priority,
        "title": title,
        "description": description[:200],
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "url": f"https://jira.company.internal/browse/{mock_id}",
        "note": "MOCK ticket — khong ton tai trong he thong that",
    }
    return ticket

# ─────────────────────────────────────────────
# In-Process Dispatch Layer
# ─────────────────────────────────────────────

TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}

def list_tools() -> list:
    """Return available tool schemas."""
    return list(TOOL_SCHEMAS.values())

def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """In-process MCP dispatch."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' khong ton tai. Available: {list(TOOL_REGISTRY.keys())}"}
    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        return tool_fn(**tool_input)
    except TypeError as e:
        return {"error": f"Invalid input for '{tool_name}': {e}", "schema": TOOL_SCHEMAS[tool_name]["inputSchema"]}
    except Exception as e:
        return {"error": f"Tool '{tool_name}' failed: {e}"}

# ─────────────────────────────────────────────
# FastAPI HTTP Server
# ─────────────────────────────────────────────

def create_fastapi_app():
    from fastapi import FastAPI, HTTPException, Request
    app = FastAPI(title="Helpdesk MCP Server")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed_ms = round((time.time() - start) * 1000, 1)
        print(f"[MCP] {datetime.now().isoformat()} | {request.method} {request.url.path} | {response.status_code} | {elapsed_ms}ms")
        return response

    @app.get("/tools")
    async def get_tools():
        return {"tools": list_tools(), "count": len(TOOL_SCHEMAS)}

    @app.post("/tools/call/{tool_name}")
    async def call_tool(tool_name: str, request: Request):
        if tool_name not in TOOL_REGISTRY:
            raise HTTPException(status_code=404, detail={"error": "Tool not found"})
        try:
            body = await request.json()
        except:
            body = {}
        result = dispatch_tool(tool_name, body)
        return {"tool": tool_name, "output": result}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app

if __name__ == "__main__":
    if sys.platform == "win32":
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

    import uvicorn
    app = create_fastapi_app()
    print("=" * 60)
    print("MCP HTTP Server — TIP-005 (FastAPI)")
    print("=" * 60)
    print("Starting on http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
