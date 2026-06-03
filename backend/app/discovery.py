from playwright.async_api import async_playwright, Page
from pydantic import BaseModel


class DOMElement(BaseModel):
    tag: str
    id: str | None = None
    text: str | None = None
    href: str | None = None
    type: str | None = None  # For inputs
    name: str | None = None
    selector: str
    class_name: str | None = None  # Added for better selectors
    role: str | None = None  # For accessibility


class PageStructure(BaseModel):
    url: str
    title: str
    elements: list[DOMElement]


def _generate_selector(element: dict) -> str:
    """Generate a robust CSS selector for an element."""
    # Priority: ID > class + tag > tag + attribute > tag
    if element.get("id"):
        return f"#{element['id']}"

    tag = element["tag"]

    # For inputs, prefer name or type
    if tag in ["input", "textarea", "select"]:
        if element.get("name"):
            return f"{tag}[name='{element['name']}']"
        if element.get("type"):
            return f"{tag}[type='{element['type']}']"

    # For links and buttons, try to use class or text content
    classes = element.get("class")
    if classes:
        return f"{tag}.{classes.replace(' ', '.')}"

    # For accessibility
    role = element.get("role")
    if role:
        return f"[role='{role}']"

    # Fallback to tag with basic selector
    return tag


def _element_score(element: dict) -> int:
    """Score elements by their likely importance for testing."""
    score = 0
    tag = element.get("tag", "")
    text = (element.get("text") or "").strip().lower()

    # High value elements
    if tag == "button":
        score += 10
        # Buttons with clear text are better
        if text and text not in ["click", "more", "read more", "learn more"]:
            score += 5
        if element.get("id"):
            score += 3

    if tag in ["input", "textarea", "select"]:
        score += 8
        if element.get("name"):
            score += 3

    if tag == "a":
        score += 5
        # Links with descriptive text are better
        if text and len(text) > 10 and text not in ["click here", "more", "read more"]:
            score += 3
        if element.get("id"):
            score += 3

    # Accessibility support
    if element.get("role"):
        score += 2

    return score


async def discover_page_structure(url: str) -> PageStructure:
    """Extract the structure of a page - interactive elements only."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            title = await page.title()
            final_url = page.url

            # Extract interactive elements with more context
            raw_elements = await page.evaluate("""() => {
                const elements = [];
                const seen = new Set(); // For deduplication

                // Helper to generate a unique key for deduplication
                const getKey = (el) => {
                    return `${el.tagName}:${el.id || ''}:${el.className || ''}:${el.textContent?.slice(0, 20) || ''}`;
                };

                // Links
                document.querySelectorAll('a[href]').forEach(el => {
                    const key = getKey(el);
                    if (!seen.has(key) && el.offsetWidth > 0 && el.offsetHeight > 0) {
                        seen.add(key);
                        elements.push({
                            tag: 'a',
                            id: el.id || null,
                            text: el.textContent?.slice(0, 50).trim() || null,
                            href: el.href,
                            class: el.className || null,
                            role: el.getAttribute('role') || null
                        });
                    }
                });

                // Buttons
                document.querySelectorAll('button').forEach(el => {
                    const key = getKey(el);
                    if (!seen.has(key) && el.offsetWidth > 0 && el.offsetHeight > 0) {
                        seen.add(key);
                        elements.push({
                            tag: 'button',
                            id: el.id || null,
                            text: el.textContent?.slice(0, 50).trim() || null,
                            type: el.type || null,
                            class: el.className || null,
                            role: el.getAttribute('role') || null
                        });
                    }
                });

                // Inputs
                document.querySelectorAll('input, textarea, select').forEach(el => {
                    const key = getKey(el);
                    if (!seen.has(key) && el.offsetWidth > 0 && el.offsetHeight > 0) {
                        seen.add(key);
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            id: el.id || null,
                            type: el.type || null,
                            name: el.name || null,
                            class: el.className || null,
                            role: el.getAttribute('role') || null
                        });
                    }
                });

                // Forms
                document.querySelectorAll('form').forEach(el => {
                    const key = getKey(el);
                    if (!seen.has(key)) {
                        seen.add(key);
                        elements.push({
                            tag: 'form',
                            id: el.id || null,
                            class: el.className || null
                        });
                    }
                });

                return elements;
            }""")

            # Convert to DOMElement objects with better selectors
            elements_with_scores = []
            for el in raw_elements:
                dom_element = DOMElement(
                    tag=el["tag"],
                    id=el.get("id"),
                    text=el.get("text"),
                    href=el.get("href"),
                    type=el.get("type"),
                    name=el.get("name"),
                    selector=_generate_selector(el),
                    class_name=el.get("class"),
                    role=el.get("role")
                )
                score = _element_score(el)
                elements_with_scores.append((dom_element, score))

            # Sort by score (most important first) and take top 20
            elements_with_scores.sort(key=lambda x: x[1], reverse=True)
            top_elements = [el for el, _ in elements_with_scores[:20]]

            return PageStructure(
                url=final_url,
                title=title,
                elements=top_elements
            )
        finally:
            await browser.close()
