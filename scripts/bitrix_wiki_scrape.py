#!/usr/bin/env python3
import argparse
import glob
import html as html_mod
import json
import os
import re
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


def fetch_url(url: str, timeout: int = 20) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "AgentSkillsBitrixWiki/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")

def fetch_url_cached(url: str, cache_dir: str, timeout: int = 20) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    key = sanitize_filename(url) + ".html"
    path = os.path.join(cache_dir, key)
    if os.path.isfile(path):
        return read_text(path)
    html = fetch_url(url, timeout=timeout)
    write_text(path, html)
    return html

def load_registry_urls(base_urls: list[str]) -> list[str]:
    all_urls = []
    for base in base_urls:
        try:
            html = fetch_url(base)
        except Exception:
            continue
        m = re.search(r'(_search/ru/[^"]+-resources\\.js)', html)
        if not m:
            continue
        resources_url = urljoin(base, m.group(1))
        try:
            resources_js = fetch_url(resources_url)
        except Exception:
            continue
        m2 = re.search(r'"registry":"([^"]+)"', resources_js)
        if not m2:
            continue
        registry_url = urljoin(base, m2.group(1))
        try:
            registry_js = fetch_url(registry_url)
        except Exception:
            continue
        registry_js = registry_js.strip()
        if not registry_js.startswith("self.registry="):
            continue
        raw = registry_js[len("self.registry="):]
        if raw.endswith(";"):
            raw = raw[:-1]
        try:
            registry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for key in registry.keys():
            all_urls.append(urljoin(base, key))
    return sorted(set(all_urls))

def read_last_registry(path: str) -> set[str]:
    if not os.path.isfile(path):
        return set()
    try:
        data = json.loads(read_text(path))
    except Exception:
        return set()
    return set(data.get("urls", []))

def write_registry_snapshot(path: str, urls: list[str]) -> None:
    write_json(path, {"urls": sorted(set(urls))})


def html_to_text(html: str) -> str:
    html = re.sub(r"(?s)<script.*?>.*?</script>", "", html)
    html = re.sub(r"(?s)<style.*?>.*?</style>", "", html)
    html = re.sub(r"(?s)<title[^>]*>(.*?)</title>", r"# \1\n\n", html)
    html = re.sub(r"(?s)<h1[^>]*>(.*?)</h1>", r"# \1\n\n", html)
    html = re.sub(r"(?s)<h2[^>]*>(.*?)</h2>", r"## \1\n\n", html)
    html = re.sub(r"(?s)<h3[^>]*>(.*?)</h3>", r"### \1\n\n", html)
    html = re.sub(r"(?s)<pre><code[^>]*>(.*?)</code></pre>", r"```\n\1\n```\n\n", html)
    html = re.sub(r"(?s)<br\s*/?>", "\n", html)
    html = re.sub(r"</p\s*>", "\n\n", html)
    html = re.sub(r"</h[1-6]\s*>", "\n\n", html)
    html = re.sub(r"<[^>]+>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def sanitize_filename(url: str) -> str:
    parsed = urlparse(url)
    slug = (parsed.netloc + parsed.path).strip("/").replace("/", "__")
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", slug)
    if not slug:
        slug = "page"
    return slug


def write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def title_from_markdown(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback

def classify_entity(url: str, title: str) -> str:
    u = url.lower()
    t = title.lower()
    if "event" in u or "event" in t:
        return "event"
    if "component" in u or "component" in t:
        return "component"
    if "module" in u or "module" in t:
        return "module"
    if "rest" in u or "method" in u or "rest" in t or "method" in t:
        return "method"
    return "guide"

def extract_diplodoc_json(html: str) -> dict | None:
    m = re.search(r'<script type="application/json" id="diplodoc-state">\s*(\{.*?\})\s*</script>', html, re.S)
    if not m:
        return None
    raw = m.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def diplodoc_html(state: dict) -> str:
    html = state.get("data", {}).get("html", "")
    return html_mod.unescape(html)

def diplodoc_title(state: dict, fallback: str) -> str:
    title = state.get("data", {}).get("title", "")
    if title:
        return title
    return fallback

def diplodoc_meta_fields(state: dict) -> dict:
    html = diplodoc_html(state)
    scope = ""
    who = ""
    m = re.search(r"Scope:\s*(.*?)</p>", html, re.S)
    if m:
        scope = strip_tags(m.group(1))
    m2 = re.search(r"Кто может выполнять метод:\s*(.*?)</p>", html, re.S)
    if m2:
        who = strip_tags(m2.group(1))
    scopes = []
    if scope:
        # split by comma and normalize
        for part in re.split(r",\s*", scope):
            part = part.strip()
            if part:
                scopes.append(part)
    return {"scope": scopes, "who_can_execute": who}
def extract_links_from_state(state: dict) -> list[str]:
    links = []
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "url" and isinstance(v, str):
                    links.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(state)
    return links

def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return html_mod.unescape(s).strip()

def parse_table(html: str) -> list[list[str]]:
    rows = []
    for tr in re.findall(r"(?s)<tr>(.*?)</tr>", html):
        cols = [strip_tags(td) for td in re.findall(r"(?s)<td>(.*?)</td>", tr)]
        if cols:
            rows.append(cols)
    return rows

def find_section_table(html: str, heading_title: str) -> list[list[str]]:
    pattern = re.compile(
        rf"<h[23][^>]*>.*?{re.escape(heading_title)}.*?</h[23]>(.*?)<h[23][^>]*>|"
        rf"<h[23][^>]*>.*?{re.escape(heading_title)}.*?</h[23]>(.*)$",
        re.S,
    )
    m = pattern.search(html)
    if not m:
        return []
    section = m.group(1) or ""
    mtable = re.search(r"(?s)<table>(.*?)</table>", section)
    if not mtable:
        return []
    return parse_table(mtable.group(1))

def normalize_params(rows: list[list[str]]) -> list[dict]:
    out = []
    if not rows:
        return out
    for cols in rows[1:]:
        if len(cols) < 2:
            continue
        if not cols[0].strip():
            continue
        name = cols[0].split()[0]
        ptype = ""
        tokens = cols[0].split()
        if len(tokens) >= 2:
            ptype = tokens[-1]
        out.append({"name": name, "type": ptype, "description": cols[1]})
    return out

def parse_nested_params(html: str) -> dict:
    nested = {}
    # Sections like "Параметр data", "Параметр PARAMS"
    pattern = re.compile(
        r"<h3[^>]*>\s*Параметр\s+([^<]+)</h3>(.*?)<h3[^>]*>|<h3[^>]*>\s*Параметр\s+([^<]+)</h3>(.*)$",
        re.S,
    )
    for m in pattern.finditer(html):
        name = (m.group(1) or m.group(3) or "").strip()
        section = m.group(2) or m.group(4) or ""
        t = re.search(r"(?s)<table>(.*?)</table>", section)
        if not t:
            continue
        rows = parse_table(t.group(1))
        nested[name] = normalize_params(rows)
    return nested

def flatten_nested_params(nested: dict) -> list[dict]:
    flat = []
    for group, params in nested.items():
        for p in params:
            item = dict(p)
            item["group"] = group
            flat.append(item)
    return flat
def normalize_returns(rows: list[list[str]]) -> list[dict]:
    return normalize_params(rows)

def normalize_errors(rows: list[list[str]]) -> list[dict]:
    out = []
    if not rows:
        return out
    for cols in rows[1:]:
        if len(cols) < 3:
            continue
        out.append({"status": cols[0], "code": cols[1], "description": cols[2]})
    return out

def mark_system_errors(html: str, errors: list[dict]) -> list[dict]:
    # If errors table is under "Статусы и коды системных ошибок", mark as system
    if re.search(r"Статусы и коды системных ошибок", html):
        for e in errors:
            e["is_system_error"] = True
    return errors

def extract_code_examples(html: str, limit: int = 5) -> list[dict]:
    examples = []
    # Capture tabs with labels when available
    tab_blocks = re.findall(r'(?s)<div[^>]*class="yfm-tab-panel[^"]*"[^>]*data-title="([^"]+)"[^>]*>.*?<pre><code[^>]*>(.*?)</code></pre>', html)
    for title, code in tab_blocks:
        text = html_mod.unescape(code).strip()
        if text:
            examples.append({"code": text, "language": title.strip()})
        if len(examples) >= limit:
            return examples
    for code in re.findall(r"(?s)<pre><code[^>]*>(.*?)</code></pre>", html):
        text = html_mod.unescape(code).strip()
        if text:
            examples.append({"code": text, "language": ""})
        if len(examples) >= limit:
            break
    return examples

def extract_method_name(title: str) -> str:
    m = re.findall(r"[a-z0-9_]+\.[a-z0-9_]+", title.lower())
    return m[-1] if m else ""

def build_entity_from_apidocs(url: str, html: str, fallback_slug: str) -> dict:
    state = extract_diplodoc_json(html)
    if not state:
        return {}
    page_html = diplodoc_html(state)
    title = diplodoc_title(state, fallback_slug)
    meta = diplodoc_meta_fields(state)
    params_rows = find_section_table(page_html, "Параметры метода")
    returns_rows = find_section_table(page_html, "Возвращаемые данные")
    errors_rows = find_section_table(page_html, "Статусы и коды системных ошибок")
    method_name = extract_method_name(title)
    etype = "method" if method_name else "guide"
    tags = []
    msec = re.search(r"/api-reference/([^/]+)/", url)
    if msec:
        tags.append(msec.group(1))
    return {
        "id": fallback_slug,
        "type": etype,
        "title": title,
        "summary": "",
        "source_url": url,
        "source_type": "web",
        "source_repo": "",
        "source_path": "",
        "last_updated": "",
        "tags": tags,
        "body_md_path": "",
        "meta": meta,
        "params": normalize_params(params_rows),
        "params_nested": parse_nested_params(page_html),
        "params_nested_flat": flatten_nested_params(parse_nested_params(page_html)),
        "returns": normalize_returns(returns_rows),
        "examples": extract_code_examples(page_html),
        "errors": mark_system_errors(page_html, normalize_errors(errors_rows)),
    }

def crawl_apidocs(base_urls: list[str], sections: list[str], limit: int = 200) -> list[str]:
    urls = []
    # Try registry-based discovery for Diplodoc
    for base in base_urls:
        try:
            html = fetch_url(base)
        except Exception:
            continue
        m = re.search(r'(_search/ru/[^"]+-resources\.js)', html)
        if not m:
            continue
        resources_url = urljoin(base, m.group(1))
        try:
            resources_js = fetch_url(resources_url)
        except Exception:
            continue
        m2 = re.search(r'"registry":"([^"]+)"', resources_js)
        if not m2:
            continue
        registry_url = urljoin(base, m2.group(1))
        try:
            registry_js = fetch_url(registry_url)
        except Exception:
            continue
        registry_js = registry_js.strip()
        if not registry_js.startswith("self.registry="):
            continue
        raw = registry_js[len("self.registry="):]
        if raw.endswith(";"):
            raw = raw[:-1]
        try:
            registry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for key in registry.keys():
            if not key.startswith("api-reference/"):
                continue
            if "*" in sections:
                urls.append(urljoin(base, key))
                continue
            for section in sections:
                if key.startswith(f"api-reference/{section}/"):
                    urls.append(urljoin(base, key))
        if urls:
            return sorted(set(urls))[:limit]

    visited = set()
    queue = list(base_urls)
    while queue and len(visited) < limit:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            html = fetch_url(url)
        except Exception:
            continue
        state = extract_diplodoc_json(html)
        if not state:
            continue
        links = extract_links_from_state(state)
        for link in links:
            full = link if link.startswith("http") else urljoin(url, link)
            if "apidocs.bitrix24.ru" not in full:
                continue
            if "/api-reference/" not in full:
                continue
            urls.append(full)
            if full not in visited:
                queue.append(full)
    # keep only section pages
    out = []
    for u in sorted(set(urls)):
        if not u.endswith(".html"):
            continue
        if "*" in sections:
            out.append(u)
            continue
        for section in sections:
            if f"/api-reference/{section}/" in u:
                out.append(u)
                break
    return out
def collect_markdown_files(root: str, patterns: list[str]) -> list[str]:
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(root, pattern), recursive=True))
    return sorted(set(p for p in files if os.path.isfile(p)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and store Bitrix docs pages.")
    parser.add_argument("--url", action="append", help="Page URL to fetch")
    parser.add_argument("--config", help="Path to config JSON")
    parser.add_argument("--out", required=True, help="Output root folder")
    parser.add_argument("--cache", help="Cache directory for fetched HTML")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    sources_dir = os.path.join(args.out, "sources")
    wiki_dir = os.path.join(args.out, "wiki")
    api_dir = os.path.join(args.out, "api")
    os.makedirs(sources_dir, exist_ok=True)
    os.makedirs(wiki_dir, exist_ok=True)
    os.makedirs(api_dir, exist_ok=True)

    entities = []

    urls = []
    git_sources = []
    apidocs_sections = []
    apidocs_base_urls = []
    apidocs_limit = 200
    if args.config:
        cfg = json.loads(read_text(args.config))
        for src in cfg.get("sources", []):
            if src.get("type") == "git":
                git_sources.append(src)
            else:
                urls.extend(src.get("urls", []))
                if "apidocs.bitrix24.ru" in " ".join(src.get("urls", [])):
                    apidocs_sections = src.get("crawl_sections", [])
                    apidocs_base_urls = src.get("urls", [])
                    apidocs_limit = int(src.get("crawl_limit", 200))
    if args.url:
        urls.extend(args.url)

    extra_urls = []
    registry_snapshot = os.path.join(args.out, "sources", "_registry_snapshot.json")
    all_registry_urls = []
    if apidocs_base_urls:
        all_registry_urls = load_registry_urls(apidocs_base_urls)
    if apidocs_sections and apidocs_base_urls:
        extra_urls.extend(crawl_apidocs(apidocs_base_urls, apidocs_sections, apidocs_limit))

    if all_registry_urls:
        prev = read_last_registry(registry_snapshot)
        curr = set(all_registry_urls)
        changed = sorted(curr - prev)
        if changed:
            extra_urls.extend(changed)
        write_registry_snapshot(registry_snapshot, all_registry_urls)

    cache_dir = args.cache or os.path.join(args.out, "sources", "_cache")

    for url in urls:
        html = fetch_url_cached(url, cache_dir)
        text = html_to_text(html)
        slug = sanitize_filename(url)

        raw_path = os.path.join(sources_dir, f"{slug}.html")
        md_path = os.path.join(wiki_dir, f"{slug}.md")
        md_rel_path = os.path.relpath(md_path, args.out)
        write_text(raw_path, html)
        write_text(md_path, text + "\n")

        title = title_from_markdown(text, slug)
        base_entity = {
            "id": slug,
            "type": classify_entity(url, title),
            "title": title,
            "summary": "",
            "source_url": url,
            "source_type": "web",
            "source_repo": "",
            "source_path": "",
            "last_updated": "",
            "tags": [],
            "body_md_path": md_rel_path,
            "params": {},
            "returns": {},
            "examples": [],
            "errors": [],
        }
        if "apidocs.bitrix24.ru/api-reference/" in url:
            parsed = build_entity_from_apidocs(url, html, slug)
            if parsed:
                parsed["body_md_path"] = md_rel_path
                entities.append(parsed)
            else:
                entities.append(base_entity)
        else:
            entities.append(base_entity)

    for url in sorted(set(extra_urls)):
        if url in urls:
            continue
        html = fetch_url_cached(url, cache_dir)
        text = html_to_text(html)
        slug = sanitize_filename(url)
        raw_path = os.path.join(sources_dir, f"{slug}.html")
        md_path = os.path.join(wiki_dir, f"{slug}.md")
        md_rel_path = os.path.relpath(md_path, args.out)
        write_text(raw_path, html)
        write_text(md_path, text + "\n")
        parsed = build_entity_from_apidocs(url, html, slug)
        if parsed:
            parsed["body_md_path"] = md_rel_path
            entities.append(parsed)
        else:
            entities.append(
                {
                    "id": slug,
                    "type": classify_entity(url, title_from_markdown(text, slug)),
                    "title": title_from_markdown(text, slug),
                    "summary": "",
                    "source_url": url,
                    "source_type": "web",
                    "source_repo": "",
                    "source_path": "",
                    "last_updated": "",
                    "tags": [],
                    "body_md_path": md_rel_path,
                    "params": {},
                    "returns": {},
                    "examples": [],
                    "errors": [],
                }
            )

    for src in git_sources:
        repo_path = src.get("path", "")
        if not repo_path or not os.path.isdir(repo_path):
            continue
        patterns = src.get("include", ["**/*.md"])
        files = collect_markdown_files(repo_path, patterns)
        for path in files:
            md = read_text(path)
            rel_path = os.path.relpath(path, repo_path)
            slug = sanitize_filename(f"{src.get('repo_url','repo')}::{rel_path}")
            md_path = os.path.join(wiki_dir, f"{slug}.md")
            md_rel_path = os.path.relpath(md_path, args.out)
            write_text(md_path, md + ("\n" if not md.endswith("\n") else ""))

            entities.append(
                {
                    "id": slug,
                    "type": classify_entity(src.get("repo_url", ""), title_from_markdown(md, os.path.basename(path))),
                    "title": title_from_markdown(md, os.path.basename(path)),
                    "summary": "",
                    "source_url": src.get("repo_url", ""),
                    "source_type": "git",
                    "source_repo": src.get("repo_url", ""),
                    "source_path": rel_path,
                    "last_updated": "",
                    "tags": [],
                    "body_md_path": md_rel_path,
                    "params": {},
                    "returns": {},
                    "examples": [],
                    "errors": [],
                }
            )

    index = {
        "version": "1.0",
        "generated_at": "2026-03-12",
        "entities": entities,
    }
    write_json(os.path.join(api_dir, "index.json"), index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
