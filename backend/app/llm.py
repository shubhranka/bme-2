from openai import OpenAI
from .schemas import GeneratedTest, TestAction
from .discovery import PageStructure
from .config import settings

# Initialize OpenAI client with settings from .env
client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL
) if settings.LLM_API_KEY else None


def generate_test_from_structure(page: PageStructure) -> GeneratedTest:
    """Generate a test script using the LLM based on page structure."""
    if not client:
        # Fallback: generate a basic test without LLM
        return _generate_basic_test(page)

    # Build detailed element information with better context
    elements_summary = []
    for i, el in enumerate(page.elements[:15]):  # Limit to 15 most relevant elements
        details = []
        details.append(f"#{i+1}")
        details.append(f"Tag: {el.tag}")

        if el.id:
            details.append(f"ID: '{el.id}'")
        if el.text and el.text.strip():
            details.append(f"Text: '{el.text.strip()[:50]}'")
        if el.href:
            details.append(f"Href: '{el.href}'")
        if el.type:
            details.append(f"Type: '{el.type}'")
        if el.name:
            details.append(f"Name: '{el.name}'")

        details.append(f"Selector: '{el.selector}'")
        elements_summary.append(" | ".join(details))

    elements_text = "\n".join(elements_summary)

    prompt = f"""You are an expert QA engineer. Generate a SIMPLE, CONSERVATIVE Playwright test for this webpage.

PAGE INFO:
- URL: {page.url}
- Title: {page.title}

INTERACTIVE ELEMENTS (top 15):
{elements_text}

RULES FOR A GOOD TEST:
1. Start with 'navigate' to the page URL
2. ONLY interact with elements that have CLEAR, VISIBLE text or clear purpose
3. AVOID elements with generic text like "click here", "more", "read more" unless it's a standard navigation element
4. PREFER elements with descriptive IDs or clear, unique text
5. Include 'wait' after navigations and clicks to ensure page stability
6. Add simple assertions like checking if key elements are visible
7. Keep it to 3-5 steps MAX - quality over quantity

CONSERVATIVE APPROACH:
- If uncertain about an element's purpose, SKIP IT
- Better to have a simple working test than a complex broken one
- Focus on the MAIN user journey (e.g., navigation, search, main action)
- Don't try to test everything - test the happy path

EXAMPLE GOOD TEST:
For a login page with username/password inputs and login button:
{{
    "description": "Test login page navigation and main elements",
    "steps": [
        {{"action_type": "navigate", "selector": "https://example.com/login", "description": "Navigate to login page"}},
        {{"action_type": "wait", "selector": "body", "description": "Wait for page to load"}},
        {{"action_type": "assert", "selector": "input[name='username']", "value": "visible", "description": "Verify username input is visible"}},
        {{"action_type": "assert", "selector": "button[type='submit']", "value": "visible", "description": "Verify submit button is visible"}}
    ]
}}

ACTION TYPES:
- navigate: selector = URL to navigate to
- click: selector = CSS selector of element to click
- fill: selector = CSS selector, value = text to fill
- wait: selector = CSS selector to wait for (use 'body' for general wait)
- assert: selector = CSS selector, value = 'visible' or element text

Respond ONLY with valid JSON matching this schema:
{{
    "description": "string - brief description of what this test does",
    "steps": [
        {{
            "action_type": "navigate|click|fill|assert|wait",
            "selector": "string - CSS selector or URL",
            "value": "string|null - for fill actions or assertions",
            "description": "string|null - what this step does"
        }}
    ]
}}"""

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a senior QA engineer specializing in web automation. Generate simple, reliable Playwright tests. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.3,  # Lower temperature for more consistent results
        )

        # Extract JSON from response
        content = response.choices[0].message.content or "{}"
        generated = GeneratedTest.model_validate_json(content)

        # Validate the generated test
        if not generated.steps or len(generated.steps) == 0:
            raise ValueError("No steps generated")

        # Ensure first step is navigate
        if generated.steps[0].action_type != "navigate":
            generated.steps.insert(0, TestAction(
                action_type="navigate",
                selector=page.url,
                description=f"Navigate to {page.url}"
            ))

        return generated

    except Exception as e:
        print(f"LLM generation failed: {e}")
        return _generate_basic_test(page)


def _generate_basic_test(page: PageStructure) -> GeneratedTest:
    """Generate a basic test without LLM (fallback)."""
    steps = [
        TestAction(
            action_type="navigate",
            selector=page.url,
            description="Navigate to page"
        ),
        TestAction(
            action_type="wait",
            selector="body",
            description="Wait for page to load"
        ),
    ]

    # Add a click if we found any links or buttons
    for el in page.elements:
        if el.tag in ["a", "button"] and el.text:
            steps.append(TestAction(
                action_type="click",
                selector=el.selector,
                description=f"Click on {el.tag}: {el.text[:30]}"
            ))
            break

    # Add an assertion
    steps.append(TestAction(
        action_type="assert",
        selector="body",
        value="visible",
        description="Verify page loaded"
    ))

    return GeneratedTest(
        description=f"Basic test for {page.title}",
        steps=steps
    )
