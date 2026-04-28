import json
from pathlib import Path

from langchain_core.tools import tool

from src.config import ORDERS_PATH, POLICIES_DIR, PRODUCTS_PATH, SKILLS_DIR


ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_json(path_str: str) -> list[dict]:
    with (ROOT_DIR / path_str).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@tool
def load_skill(skill_name: str) -> str:
    """Read and return a skill file from the skills directory."""
    skill_path = ROOT_DIR / SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_name}")
    return skill_path.read_text(encoding="utf-8")


@tool
def lookup_order(order_id: str) -> dict | None:
    """Look up an order by its order_id in the local mock dataset."""
    orders = _load_json(ORDERS_PATH)
    target = order_id.strip().upper()
    for order in orders:
        if order["order_id"].upper() == target:
            return order
    return None


@tool
def search_policy(query: str) -> str:
    """Run a simple keyword search across policy markdown files and return relevant paragraphs."""
    keywords = [token.lower() for token in query.split() if token.strip()]
    matches: list[str] = []
    policy_dir = ROOT_DIR / POLICIES_DIR
    for file_path in sorted(policy_dir.glob("*.md")):
        content = file_path.read_text(encoding="utf-8")
        paragraphs = [part.strip() for part in content.split("\n\n") if part.strip()]
        for paragraph in paragraphs:
            haystack = paragraph.lower()
            if not keywords or any(keyword in haystack for keyword in keywords):
                matches.append(f"[{file_path.stem}] {paragraph}")
    if matches:
        return "\n\n".join(matches[:6])
    return "No directly relevant policy section was found."


@tool
def search_products(query: str) -> list[dict]:
    """Run a simple keyword search over the local product catalog."""
    products = _load_json(PRODUCTS_PATH)
    keywords = [token.lower() for token in query.split() if token.strip()]
    if not keywords:
        return products[:5]

    scored: list[tuple[int, dict]] = []
    for product in products:
        searchable_parts = [
            product.get("id", ""),
            product.get("name_en", ""),
            product.get("name_ar", ""),
            product.get("category", ""),
            product.get("subcategory", ""),
            product.get("brand", ""),
            product.get("description_en", ""),
            product.get("description_ar", ""),
            " ".join(product.get("tags", [])),
        ]
        haystack = " ".join(searchable_parts).lower()
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda item: (-item[0], item[1]["name_en"]))
    return [product for _, product in scored[:8]]
