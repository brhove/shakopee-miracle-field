#!/usr/bin/env python3
"""
Transform miracle-field-website.html into a Squarespace-ready version.
Uses a robust CSS parser approach instead of line-by-line parsing.
"""

import re
import base64
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "miracle-field-website.html")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "miracle-field-squarespace.html")
LOGO_FILE = os.path.join(SCRIPT_DIR, "miracle-league-logo.png")

# Read the logo and convert to base64
with open(LOGO_FILE, "rb") as f:
    logo_b64 = base64.b64encode(f.read()).decode("utf-8")
LOGO_DATA_URI = f"data:image/png;base64,{logo_b64}"

# Read the original HTML
with open(INPUT_FILE, "r") as f:
    html = f.read()

# Extract CSS and body
css_match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
body_match = re.search(r"<body>(.*?)</body>", html, re.DOTALL)
original_css = css_match.group(1)
body_content = body_match.group(1)

# Replace logo references with base64
body_content = body_content.replace('src="miracle-league-logo.png"', f'src="{LOGO_DATA_URI}"')


def process_css_for_squarespace(css_text):
    """
    Process CSS to scope under .mf-page and add !important.
    Uses a tokenizer approach to handle complex CSS properly.
    """
    # Step 1: Extract and protect @keyframes blocks
    keyframes = {}
    kf_counter = 0

    def replace_keyframe(match):
        nonlocal kf_counter
        kf_counter += 1
        key = f"__KEYFRAME_{kf_counter}__"
        keyframes[key] = match.group(0)
        return key

    css = re.sub(r'@keyframes\s+\w+\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', replace_keyframe, css_text)

    # Step 2: Process @media blocks
    # Find media queries and process selectors inside them
    def process_media_block(match):
        media_rule = match.group(1)  # e.g., "@media (max-width: 900px)"
        content = match.group(2)     # content inside {}

        # Process each rule inside the media block
        processed = process_rules(content, indent="      ")
        return f"    {media_rule} {{\n{processed}\n    }}"

    # Step 3: Process regular CSS rules
    def process_rules(css_block, indent="    "):
        """Process CSS rules: scope selectors and add !important to values."""
        result = []

        # Split into individual rules
        # Find rule blocks: selector { properties }
        pos = 0
        while pos < len(css_block):
            # Skip whitespace and comments
            if css_block[pos:pos+2] == '/*':
                end = css_block.find('*/', pos)
                if end == -1:
                    result.append(css_block[pos:])
                    break
                result.append(css_block[pos:end+2])
                pos = end + 2
                continue

            if css_block[pos] in ' \t\n\r':
                result.append(css_block[pos])
                pos += 1
                continue

            # Check for keyframe placeholder
            kf_match = re.match(r'__KEYFRAME_\d+__', css_block[pos:])
            if kf_match:
                result.append(css_block[pos:pos+kf_match.end()])
                pos += kf_match.end()
                continue

            # Check for @media
            media_match = re.match(r'(@media[^{]+)\{', css_block[pos:])
            if media_match:
                # Find matching closing brace
                brace_start = pos + media_match.end()
                depth = 1
                i = brace_start
                while i < len(css_block) and depth > 0:
                    if css_block[i] == '{':
                        depth += 1
                    elif css_block[i] == '}':
                        depth -= 1
                    i += 1
                media_content = css_block[brace_start:i-1]
                media_rule = media_match.group(1).strip()
                processed_content = process_rules(media_content, indent + "  ")
                result.append(f"\n{indent}{media_rule} {{\n{processed_content}\n{indent}}}")
                pos = i
                continue

            # Find a CSS rule: selector { declarations }
            brace_pos = css_block.find('{', pos)
            if brace_pos == -1:
                result.append(css_block[pos:])
                break

            selector = css_block[pos:brace_pos].strip()

            if not selector:
                pos = brace_pos + 1
                continue

            # Find the matching closing brace
            depth = 1
            i = brace_pos + 1
            while i < len(css_block) and depth > 0:
                if css_block[i] == '{':
                    depth += 1
                elif css_block[i] == '}':
                    depth -= 1
                i += 1

            declarations = css_block[brace_pos+1:i-1].strip()

            # Scope the selector
            scoped_selector = scope_selector(selector)

            # Add !important to declarations
            important_declarations = add_important_to_declarations(declarations)

            result.append(f"\n{indent}{scoped_selector} {{\n{indent}  {important_declarations}\n{indent}}}")
            pos = i

        return ''.join(result)

    processed = process_rules(css)

    # Step 4: Restore @keyframes blocks
    for key, kf_block in keyframes.items():
        processed = processed.replace(key, "\n    " + kf_block)

    return processed


def scope_selector(selector):
    """Add .mf-page prefix to CSS selectors."""
    # Split by comma for grouped selectors
    parts = [s.strip() for s in selector.split(',')]
    scoped = []

    for part in parts:
        if not part:
            continue
        # :root -> .mf-page
        if part.strip() == ':root':
            scoped.append('.mf-page')
        elif part.strip().startswith(':root'):
            scoped.append(part.replace(':root', '.mf-page'))
        # html or body -> .mf-page
        elif part.strip() in ('html', 'body'):
            scoped.append('.mf-page')
        elif part.strip().startswith('html ') or part.strip().startswith('body '):
            scoped.append('.mf-page ' + part.strip().split(' ', 1)[1])
        # Universal selectors
        elif part.strip().startswith('*'):
            scoped.append('.mf-page ' + part.strip())
        # Already has . or # prefix
        elif part.strip().startswith('.') or part.strip().startswith('#'):
            scoped.append('.mf-page ' + part.strip())
        # Element selectors (a, img, p, section, etc.)
        else:
            scoped.append('.mf-page ' + part.strip())

    return ', '.join(scoped)


def add_important_to_declarations(declarations):
    """Add !important to all CSS property values."""
    if not declarations.strip():
        return declarations

    # Split by semicolons, but be careful of values with semicolons in them
    parts = declarations.split(';')
    result = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith('/*') or part.startswith('*'):
            result.append(part)
            continue

        if ':' in part:
            # Split only on the first colon
            prop, _, value = part.partition(':')
            prop = prop.strip()
            value = value.strip()

            if value and '!important' not in value:
                value = value + ' !important'

            result.append(f"{prop}: {value}")
        else:
            result.append(part)

    return ';\n      '.join(result) + ';' if result else ''


# Process the CSS
processed_css = process_css_for_squarespace(original_css)

# Squarespace reset CSS
squarespace_reset = """
    /* ========================================
       SQUARESPACE OVERRIDE RESET
       ======================================== */
    .mf-page,
    .mf-page *,
    .mf-page *::before,
    .mf-page *::after {
      box-sizing: border-box !important;
    }

    .mf-page {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
      color: #1F2937 !important;
      line-height: 1.6 !important;
      -webkit-font-smoothing: antialiased !important;
      width: 100% !important;
      max-width: none !important;
    }

    .mf-page a {
      color: #003D7C !important;
      text-decoration: none !important;
      background-color: transparent !important;
    }

    .mf-page a:hover {
      text-decoration: none !important;
    }

    .mf-page img {
      max-width: 100% !important;
      display: block !important;
      border: none !important;
    }

    .mf-page h1,
    .mf-page h2,
    .mf-page h3,
    .mf-page h4,
    .mf-page h5,
    .mf-page h6 {
      letter-spacing: normal !important;
    }

    .mf-page p {
      margin-top: 0 !important;
      margin-bottom: 0 !important;
    }

    .mf-page ul {
      list-style: none !important;
      padding-left: 0 !important;
    }

    .mf-page section {
      border: none !important;
    }

    /* Force button styles against Squarespace overrides */
    .mf-page .btn,
    .mf-page a.btn,
    .mf-page a.btn:visited,
    .mf-page a.btn:link {
      -webkit-appearance: none !important;
      -moz-appearance: none !important;
      appearance: none !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      padding: 14px 28px !important;
      border-radius: 12px !important;
      font-weight: 700 !important;
      font-size: 15px !important;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
      transition: all 0.2s ease !important;
      cursor: pointer !important;
      border: 2px solid transparent !important;
      text-decoration: none !important;
      line-height: 1.4 !important;
    }

    .mf-page a.btn-primary,
    .mf-page a.btn-primary:visited,
    .mf-page a.btn-primary:link {
      background-color: #F5A623 !important;
      background-image: none !important;
      color: #002B5C !important;
      border-color: #F5A623 !important;
    }

    .mf-page a.btn-primary:hover {
      background-color: #FFC857 !important;
      border-color: #FFC857 !important;
      transform: translateY(-1px) !important;
      box-shadow: 0 4px 12px rgba(245,166,35,0.4) !important;
      color: #002B5C !important;
    }

    .mf-page a.btn-outline,
    .mf-page a.btn-outline:visited,
    .mf-page a.btn-outline:link {
      background-color: transparent !important;
      background-image: none !important;
      color: #FFFFFF !important;
      border-color: rgba(255,255,255,0.4) !important;
    }

    .mf-page a.btn-outline:hover {
      background-color: rgba(255,255,255,0.1) !important;
      border-color: rgba(255,255,255,0.6) !important;
      color: #FFFFFF !important;
    }

    .mf-page a.btn-dark,
    .mf-page a.btn-dark:visited,
    .mf-page a.btn-dark:link {
      background-color: #002B5C !important;
      background-image: none !important;
      color: #FFFFFF !important;
      border-color: #002B5C !important;
    }

    .mf-page a.btn-dark:hover {
      background-color: #003D7C !important;
      border-color: #003D7C !important;
      transform: translateY(-1px) !important;
      color: #FFFFFF !important;
    }

    /* Force section backgrounds against Squarespace */
    .mf-page .hero {
      background: linear-gradient(135deg, rgba(0,43,92,0.88) 0%, rgba(0,61,124,0.82) 50%, rgba(0,86,168,0.78) 100%),
                  url('https://crossbar.s3.amazonaws.com/organizations/2691/uploads/543b4a39-f3e2-46e6-9d42-6dbe8f6fa2dd.png') center/cover no-repeat !important;
      color: #FFFFFF !important;
    }

    .mf-page .hero h1,
    .mf-page .hero p,
    .mf-page .hero .hero-badge {
      color: #FFFFFF !important;
    }

    .mf-page .hero h1 span {
      color: #F5A623 !important;
    }

    .mf-page .season-banner {
      background-color: #F5A623 !important;
      background-image: none !important;
    }

    .mf-page .section-alt {
      background-color: #F9FAFB !important;
      background-image: none !important;
    }

    .mf-page .section-blue {
      background: linear-gradient(135deg, #002B5C 0%, #003D7C 100%) !important;
      color: #FFFFFF !important;
    }

    .mf-page .section-blue h2,
    .mf-page .section-blue h3,
    .mf-page .section-blue p {
      color: #FFFFFF !important;
    }

    .mf-page .cta-section {
      background: linear-gradient(135deg, #002B5C 0%, #003D7C 100%) !important;
      color: #FFFFFF !important;
    }

    .mf-page .cta-section h2,
    .mf-page .cta-section p {
      color: #FFFFFF !important;
    }

    .mf-page .footer {
      background-color: #111827 !important;
      background-image: none !important;
      color: rgba(255,255,255,0.5) !important;
    }

    .mf-page .footer a {
      color: rgba(255,255,255,0.5) !important;
    }

    .mf-page .footer a:hover {
      color: #F5A623 !important;
    }

    .mf-page .section-label {
      color: #F5A623 !important;
    }

    .mf-page .section-header h2 {
      color: #111827 !important;
    }

    .mf-page .section-blue .section-header h2 {
      color: #FFFFFF !important;
    }

    .mf-page .section-header p {
      color: #4B5563 !important;
    }

    .mf-page .section-blue .section-header p {
      color: rgba(255,255,255,0.8) !important;
    }

    .mf-page .cta-contact-item a {
      color: #F5A623 !important;
    }
"""

# Build the final output
output = f"""<!-- MIRACLE FIELD OF SHAKOPEE - SQUARESPACE VERSION -->
<!-- Paste this entire block into a Squarespace Code Block -->
<!-- Generated on {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')} -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Playfair+Display:wght@700;800&display=swap" rel="stylesheet">
<style>
{squarespace_reset}
{processed_css}
</style>
<div class="mf-page">
{body_content}
</div>
"""

with open(OUTPUT_FILE, "w") as f:
    f.write(output)

print(f"✅ Squarespace version created: {OUTPUT_FILE}")
print(f"   File size: {os.path.getsize(OUTPUT_FILE):,} bytes")
print(f"   Logo embedded as base64 ({len(logo_b64):,} chars)")
