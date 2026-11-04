from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sqlalchemy import text

from .common import as_json, ensure_capstone_tables, make_engine, seed_reference_data, server_host, server_port

mcp = FastMCP("policy-mcp", host=server_host(), port=server_port(8102))


@mcp.tool()
def get_policy(policy_number: str) -> dict:
    ensure_capstone_tables()
    seed_reference_data()
    engine = make_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT policy_number, product, wording, active
                FROM cap_policies
                WHERE policy_number = :policy_number
                """
            ),
            {"policy_number": policy_number},
        ).mappings().first()
    if not row:
        return {"error": f"Unknown policy_number: {policy_number}"}
    return dict(row)


@mcp.tool()
def check_coverage(policy_number: str, claim_type: str, amount: float) -> dict:
    policy = get_policy(policy_number)
    if "error" in policy:
        return policy

    covered = policy["product"].lower() == claim_type.lower()
    reason = "covered" if covered else f"product mismatch: policy={policy['product']} claim={claim_type}"
    return {
        "policy_number": policy_number,
        "covered": covered,
        "reason": reason,
        "amount": amount,
    }


@mcp.tool()
def search_policy_wording(product: str, query: str, limit: int = 5) -> list[dict]:
    ensure_capstone_tables()
    seed_reference_data()
    engine = make_engine()
    pattern = f"%{query.lower()}%"
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT policy_number, product, wording
                FROM cap_policies
                WHERE lower(product) = :product
                  AND lower(wording) LIKE :pattern
                LIMIT :limit
                """
            ),
            {
                "product": product.lower(),
                "pattern": pattern,
                "limit": max(1, min(limit, 20)),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


@mcp.resource("policy://{policy_number}")
def policy_resource(policy_number: str) -> str:
    return as_json(get_policy(policy_number))


@mcp.resource("policy-wording://{product}")
def policy_wording_resource(product: str) -> str:
    rows = search_policy_wording(product=product, query="", limit=25)
    return as_json(rows)


def main() -> None:
    ensure_capstone_tables()
    seed_reference_data()
    mcp.run("stdio")


if __name__ == "__main__":
    main()
