(() => {
  const escapeHtml = (value) => value.replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]);
  const stripEmbeddedHtml = (line) => line
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<\/?(td|th)(?:\s[^>]*)?>/gi, " ")
    .replace(/<[^>]+>/g, "");
  const slug = (value) => value.toLowerCase().replace(/<[^>]*>/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  const inline = (text, currentPath = "") => {
    let out = escapeHtml(text);
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
      if (href.endsWith(".md") || href.includes(".md#")) {
        const [rawPath, hash] = href.split("#");
        const resolved = new URL(rawPath, `https://docs.local/${currentPath}`).pathname.slice(1);
        return `<a href="docs.html?doc=${encodeURIComponent(resolved)}${hash ? `#${hash}` : ""}">${label}</a>`;
      }
      if (href.endsWith(".sclpll")) {
        const resolved = new URL(href, `https://docs.local/${currentPath}`).pathname.slice(1);
        return `<a href="content/${resolved}" target="_blank" rel="noreferrer">${label}</a>`;
      }
      const external = /^https?:/i.test(href);
      return `<a href="${href}"${external ? ' target="_blank" rel="noreferrer"' : ""}>${label}</a>`;
    });
  };
  const markdown = (source, currentPath) => {
    const lines = source.replace(/\r/g, "").split("\n"); let html = "", i = 0, inCode = false, code = [], paragraph = [], list = null;
    const flushParagraph = () => { if (paragraph.length) { html += `<p>${inline(paragraph.join(" "), currentPath)}</p>`; paragraph.length = 0; } };
    const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
    while (i < lines.length) {
      const rawLine = lines[i];
      if (rawLine.startsWith("```")) { flushParagraph(); closeList(); if (inCode) { html += `<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`; code = []; } inCode = !inCode; i++; continue; }
      if (inCode) { code.push(rawLine); i++; continue; }
      const line = stripEmbeddedHtml(rawLine);
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(stripEmbeddedHtml(lines[i + 1]))) {
        flushParagraph(); closeList(); const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((x) => x.trim());
        const head = cells(line); i += 2; let rows = ""; while (i < lines.length && /^\s*\|.*\|\s*$/.test(stripEmbeddedHtml(lines[i]))) { rows += `<tr>${cells(stripEmbeddedHtml(lines[i])).map((cell) => `<td>${inline(cell, currentPath)}</td>`).join("")}</tr>`; i++; }
        html += `<table><thead><tr>${head.map((cell) => `<th>${inline(cell, currentPath)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`; continue;
      }
      const heading = /^(#{1,4})\s+(.+?)\s*#*$/.exec(line);
      if (heading) { flushParagraph(); closeList(); const level = heading[1].length, content = inline(heading[2], currentPath), id = slug(heading[2]); html += `<h${level} id="${id}">${content}</h${level}>`; i++; continue; }
      if (/^\s*([-*+]|\d+\.)\s+/.test(line)) { flushParagraph(); const ordered = /^\s*\d+\./.test(line), kind = ordered ? "ol" : "ul"; if (list && list !== kind) closeList(); if (!list) { html += `<${kind}>`; list = kind; } html += `<li>${inline(line.replace(/^\s*(?:[-*+]|\d+\.)\s+/, ""), currentPath)}</li>`; i++; continue; }
      if (/^>\s?/.test(line)) { flushParagraph(); closeList(); html += `<blockquote>${inline(line.replace(/^>\s?/, ""), currentPath)}</blockquote>`; i++; continue; }
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { flushParagraph(); closeList(); html += "<hr>"; i++; continue; }
      if (!line.trim()) { flushParagraph(); closeList(); i++; continue; }
      paragraph.push(line.trim()); i++;
    }
    flushParagraph(); closeList(); return html;
  };

  document.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", async () => { await navigator.clipboard.writeText(button.dataset.copy); button.textContent = "Copied"; setTimeout(() => { button.textContent = "Copy"; }, 1600); }));

  const themeToggle = document.querySelector("#theme-toggle");
  if (themeToggle) {
    const syncToggle = () => {
      const isLight = document.documentElement.getAttribute("data-theme") === "light";
      themeToggle.textContent = isLight ? "☾ Dark" : "☀ Light";
      themeToggle.setAttribute("aria-pressed", String(isLight));
    };
    themeToggle.addEventListener("click", () => {
      const goingLight = document.documentElement.getAttribute("data-theme") !== "light";
      if (goingLight) document.documentElement.setAttribute("data-theme", "light");
      else document.documentElement.removeAttribute("data-theme");
      try { localStorage.setItem("sclpl-theme", goingLight ? "light" : "dark"); } catch (e) {}
      syncToggle();
    });
    syncToggle();
  }

  if (!document.body.classList.contains("docs-page")) return;
  const nav = document.querySelector("#doc-nav"), content = document.querySelector("#doc-content"), toc = document.querySelector("#toc"), search = document.querySelector("#doc-search"), crumb = document.querySelector("#crumb"), sourceLink = document.querySelector("#source-link");
  let pages = [];
  const requested = () => new URLSearchParams(location.search).get("doc") || "README.md";

  const HIGHLIGHTS = {
    "README.md": "Start here",
    "docs/concepts.md": "Concepts",
    "docs/guide/workflow-anatomy.md": "Workflow anatomy",
    "docs/playbooks/01-paginated-api-to-csv.md": "First playbook",
    "docs/reference/cli.md": "CLI reference",
  };
  const SECTIONS = [
    { test: (p) => /^docs\/[^/]+\.md$/.test(p), key: "start", label: "Overview", order: 1 },
    { test: (p) => p.startsWith("docs/guide/"), key: "guide", label: "Guide", order: 2 },
    { test: (p) => p.startsWith("docs/playbooks/"), key: "playbooks", label: "Playbooks", order: 3 },
    { test: (p) => p.startsWith("docs/reference/"), key: "reference", label: "Reference", order: 4 },
    { test: (p) => p.startsWith("sclpll-extras/"), key: "extras", label: "SCLPLL extras", order: 5 },
    { test: (p) => p.startsWith("docs/adr/"), key: "adr", label: "Architecture decisions", order: 6 },
    { test: (p) => p.startsWith("docs/cli-rebuild/"), key: "cli-rebuild", label: "Internal planning", order: 7 },
    { test: (p) => p.startsWith("docs/attic/"), key: "attic", label: "Attic (archived)", order: 8 },
    { test: (p) => p.startsWith("docs/vault/"), key: "vault", label: "Vault (internal notes)", order: 9 },
  ];
  const sectionOf = (path) => SECTIONS.find((s) => s.test(path)) || { key: "more", label: "More", order: 10 };

  const renderNav = (query = "") => {
    const selected = requested(), q = query.toLowerCase();
    const matches = (page) => `${page.title} ${page.path}`.toLowerCase().includes(q);
    const shown = pages.filter(matches);
    const link = (page, label) => `<a class="${page.path === selected ? "selected" : ""}" href="docs.html?doc=${encodeURIComponent(page.path)}">${label || page.title}</a>`;

    let html = "";
    if (!query) {
      const highlighted = Object.keys(HIGHLIGHTS).map((path) => pages.find((page) => page.path === path)).filter(Boolean);
      if (highlighted.length) html += `<section class="docs-group docs-highlights"><p>Highlights</p>${highlighted.map((page) => link(page, HIGHLIGHTS[page.path])).join("")}</section>`;
    }
    const rest = shown.filter((page) => query || !(page.path in HIGHLIGHTS));
    const groups = rest.reduce((acc, page) => { const s = sectionOf(page.path); (acc[s.key] ||= { label: s.label, order: s.order, pages: [] }).pages.push(page); return acc; }, {});
    html += Object.values(groups).sort((a, b) => a.order - b.order)
      .map((group) => `<section class="docs-group"><p>${group.label}</p>${group.pages.map((page) => link(page)).join("")}</section>`).join("");
    nav.innerHTML = html || "<p class=loading>No pages match.</p>";
  };
  const open = async () => {
    const path = requested(); content.innerHTML = "<p class=loading>Opening field manual…</p>"; toc.innerHTML = ""; renderNav(search.value);
    try { const response = await fetch(`content/${path}`); if (!response.ok) throw new Error("not found"); const source = await response.text(); content.innerHTML = markdown(source, path); crumb.textContent = path.replace(/\.md$/, "").replaceAll("/", " / ").toUpperCase(); sourceLink.href = `https://github.com/sm408/sclpl-api/blob/main/${path}`;
      toc.innerHTML = [...content.querySelectorAll("h2,h3")].map((heading) => `<a class="level-${heading.tagName.slice(1)}" href="#${heading.id}">${heading.textContent}</a>`).join(""); content.focus({ preventScroll: true });
    } catch { content.innerHTML = `<h1>Page not found</h1><p>This page is not part of the published documentation bundle. Return to the <a href="docs.html">documentation index</a>.</p>`; }
  };
  fetch("content/index.json").then((response) => response.json()).then((index) => { pages = index; renderNav(); open(); }).catch(() => { nav.innerHTML = "<p class=loading>Documentation index unavailable. Build the site before previewing it.</p>"; });
  search.addEventListener("input", () => renderNav(search.value)); window.addEventListener("popstate", open); nav.addEventListener("click", (event) => { if (event.target.matches("a")) setTimeout(open); });
})();
