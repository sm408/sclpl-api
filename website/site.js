(() => {
  const ICON_COPY = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
  const ICON_CHECK = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
  const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  const escapeHtml = (value) => value.replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]);
  const stripEmbeddedHtml = (line) => line
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<\/?(td|th)(?:\s[^>]*)?>/gi, " ")
    .replace(/<[^>]+>/g, "");
  const slug = (value) => value.toLowerCase().replace(/<[^>]*>/g, "").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

  // Populated once the docs index loads; lets inline() resolve Obsidian-style
  // [[wikilinks]], which the vault content uses throughout.
  let wikiIndex = null;

  const inline = (text, currentPath = "") => {
    let out = escapeHtml(text);
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>");
    out = out.replace(/\[\[([^\]|#]+)(#[^\]|]+)?(?:\|([^\]]+))?\]\]/g, (whole, target, heading, alias) => {
      const label = (alias || target).trim();
      const page = wikiIndex && wikiIndex.get(target.trim().toLowerCase());
      if (!page) return label;
      const hash = heading ? `#${slug(heading.slice(1))}` : "";
      return `<a href="docs.html?doc=${encodeURIComponent(page.path)}${hash}">${label}</a>`;
    });
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

  // Long, alphabetically-sorted reference tables (functions.md, expressions.md)
  // read as one undifferentiated wall -- split them into lettered sub-sections
  // with real headings once they pass a size/diversity threshold. Short or
  // single-letter-dominated tables (cli.md's "sclpl ..." rows) stay as one table.
  const TABLE_GROUP_MIN_ROWS = 12;
  const TABLE_GROUP_MIN_LETTERS = 4;

  // Obsidian/front-matter blocks ("---\ntags:\n  - foo\n---") sit at the very
  // top of every vault note. Without this they get parsed as a <hr>, a
  // paragraph, and a bullet list -- literally showing "tags" and its values
  // as the first thing on the page.
  const stripFrontmatter = (source) => {
    const m = /^---[ \t]*\r?\n[\s\S]*?\r?\n---[ \t]*\r?\n?/.exec(source);
    return m ? source.slice(m[0].length) : source;
  };

  const markdown = (source, currentPath) => {
    const lines = stripFrontmatter(source).replace(/\r/g, "").split("\n");
    let html = "", i = 0, inCode = false, codeLang = "", code = [], paragraph = [], list = null, tableGroupCounter = 0;
    const flushParagraph = () => { if (paragraph.length) { html += `<p>${inline(paragraph.join(" "), currentPath)}</p>`; paragraph.length = 0; } };
    const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
    while (i < lines.length) {
      const rawLine = lines[i];
      if (rawLine.startsWith("```")) {
        flushParagraph(); closeList();
        if (inCode) {
          html += codeLang === "mermaid" ? `<pre class="mermaid">${escapeHtml(code.join("\n"))}</pre>` : `<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`;
          code = []; codeLang = "";
        } else {
          codeLang = rawLine.slice(3).trim().toLowerCase();
        }
        inCode = !inCode; i++; continue;
      }
      if (inCode) { code.push(rawLine); i++; continue; }
      const line = stripEmbeddedHtml(rawLine);
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(stripEmbeddedHtml(lines[i + 1]))) {
        flushParagraph(); closeList();
        const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((x) => x.trim());
        const head = cells(line); i += 2;
        const bodyRows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(stripEmbeddedHtml(lines[i]))) { bodyRows.push(cells(stripEmbeddedHtml(lines[i]))); i++; }
        const theadHtml = `<thead><tr>${head.map((cell) => `<th>${inline(cell, currentPath)}</th>`).join("")}</tr></thead>`;
        const rowHtml = (row) => `<tr>${row.map((cell) => `<td>${inline(cell, currentPath)}</td>`).join("")}</tr>`;
        const firstLetter = (row) => ((row[0] || "").replace(/[`*_]/g, "").trim().charAt(0) || "#").toUpperCase();
        const distinctLetters = new Set(bodyRows.map(firstLetter)).size;
        if (bodyRows.length > TABLE_GROUP_MIN_ROWS && distinctLetters >= TABLE_GROUP_MIN_LETTERS) {
          tableGroupCounter++;
          let currentLetter = null;
          bodyRows.forEach((row) => {
            const letter = firstLetter(row);
            if (letter !== currentLetter) {
              if (currentLetter !== null) html += "</tbody></table>";
              currentLetter = letter;
              html += `<h3 id="ref-${tableGroupCounter}-${slug(letter)}">${letter}</h3><table>${theadHtml}<tbody>`;
            }
            html += rowHtml(row);
          });
          if (currentLetter !== null) html += "</tbody></table>";
        } else {
          html += `<table>${theadHtml}<tbody>${bodyRows.map(rowHtml).join("")}</tbody></table>`;
        }
        continue;
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

  const wireCopyButton = (button, getText) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(getText());
        button.innerHTML = ICON_CHECK; button.classList.add("copied"); button.setAttribute("aria-label", "Copied");
        setTimeout(() => { button.innerHTML = ICON_COPY; button.classList.remove("copied"); button.setAttribute("aria-label", "Copy"); }, 1600);
      } catch (e) {}
    });
  };

  document.querySelectorAll("[data-copy]").forEach((button) => { button.innerHTML = ICON_COPY; button.setAttribute("aria-label", "Copy"); wireCopyButton(button, () => button.dataset.copy); });

  const addCopyButtons = (root) => {
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.dataset.copyReady || pre.classList.contains("mermaid")) return;
      pre.dataset.copyReady = "1";
      const button = document.createElement("button");
      button.type = "button"; button.className = "pre-copy"; button.innerHTML = ICON_COPY; button.setAttribute("aria-label", "Copy");
      wireCopyButton(button, () => pre.textContent.replace(/\n+$/, ""));
      pre.appendChild(button);
    });
  };
  addCopyButtons(document);

  const revealTargets = [...document.querySelectorAll(".reveal")];
  if (revealTargets.length) {
    revealTargets.forEach((el, i) => el.style.setProperty("--reveal-i", i % 6));
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => { if (entry.isIntersecting) { entry.target.classList.add("in-view"); io.unobserve(entry.target); } });
      }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
      revealTargets.forEach((el) => io.observe(el));
    } else {
      revealTargets.forEach((el) => el.classList.add("in-view"));
    }
  }

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
  let flatOrder = [];
  let currentPath = null;
  const requested = () => new URLSearchParams(location.search).get("doc") || "README.md";

  const HIGHLIGHTS = {
    "README.md": "Start here",
    "docs/concepts.md": "Concepts",
    "docs/guide/workflow-anatomy.md": "Workflow anatomy",
    "docs/reference/cli.md": "CLI reference",
  };
  const SECTIONS = [
    { test: (p) => /^docs\/[^/]+\.md$/.test(p), key: "start", label: "Overview", order: 1 },
    { test: (p) => p.startsWith("docs/guide/"), key: "guide", label: "Guide", order: 2 },
    { test: (p) => p.startsWith("docs/playbooks/"), key: "playbooks", label: "Playbooks", order: 3 },
    { test: (p) => p.startsWith("docs/reference/"), key: "reference", label: "Reference", order: 4 },
    { test: (p) => p.startsWith("sclpll-extras/"), key: "extras", label: "SCLPLL extras", order: 5 },
  ];
  // docs/vault ships as its own numbered folders ("3 Concepts", "5 Guides", ...);
  // mirror that structure instead of dumping every page into one bucket.
  const vaultSection = (path) => {
    if (path === "docs/vault/README.md") return { key: "vault-0", label: "Vault", order: 5.05 };
    const m = /^docs\/vault\/(\d+)\s+([^/]+)\//.exec(path);
    if (!m) return null;
    return { key: `vault-${m[1]}`, label: `Vault · ${m[2]}`, order: 5 + Number(m[1]) / 10 };
  };
  const sectionOf = (path) => SECTIONS.find((s) => s.test(path)) || vaultSection(path) || { key: "more", label: "More", order: 20 };

  const groupPages = (list) => {
    const groups = list.reduce((acc, page) => { const s = sectionOf(page.path); (acc[s.key] ||= { label: s.label, order: s.order, pages: [] }).pages.push(page); return acc; }, {});
    return Object.values(groups).sort((a, b) => a.order - b.order);
  };

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
    html += groupPages(rest)
      .map((group) => `<details class="docs-group" open><summary>${group.label}</summary>${group.pages.map((page) => link(page)).join("")}</details>`).join("");
    nav.innerHTML = html || "<p class=loading>No pages match.</p>";
  };

  // Canonical reading order (highlights, then each section) for the prev/next
  // footer -- independent of whatever the search box currently filters to.
  const rebuildFlatOrder = () => {
    const highlighted = Object.keys(HIGHLIGHTS).map((path) => pages.find((page) => page.path === path)).filter(Boolean);
    const rest = pages.filter((page) => !(page.path in HIGHLIGHTS));
    flatOrder = [...highlighted, ...groupPages(rest).flatMap((g) => g.pages)];
  };

  const renderAdjacent = (path) => {
    const idx = flatOrder.findIndex((p) => p.path === path);
    const prev = idx > 0 ? flatOrder[idx - 1] : null;
    const next = idx >= 0 && idx < flatOrder.length - 1 ? flatOrder[idx + 1] : null;
    if (!prev && !next) return "";
    const side = (page, dir) => page
      ? `<a class="doc-adjacent-link ${dir}" href="docs.html?doc=${encodeURIComponent(page.path)}"><span class="doc-adjacent-dir">${dir === "prev" ? "← Previous" : "Next →"}</span><span class="doc-adjacent-title">${page.title}</span></a>`
      : `<span class="doc-adjacent-link ${dir} empty"></span>`;
    return `<nav class="doc-adjacent" aria-label="Adjacent pages">${side(prev, "prev")}${side(next, "next")}</nav>`;
  };

  const scrollToHash = () => {
    if (!location.hash) { content.focus({ preventScroll: true }); return; }
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target) target.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
    else content.focus({ preventScroll: true });
  };

  const renderMermaid = () => {
    const nodes = [...content.querySelectorAll(".mermaid")];
    if (!nodes.length || typeof mermaid === "undefined") return;
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    try {
      mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: isLight ? "default" : "dark", fontFamily: "DM Mono, monospace" });
      mermaid.run({ nodes }).catch(() => {});
    } catch (e) {}
  };

  const open = async () => {
    const path = requested(); content.innerHTML = "<p class=loading>Opening field manual…</p>"; toc.innerHTML = ""; renderNav(search.value);
    try {
      const response = await fetch(`content/${path}`); if (!response.ok) throw new Error("not found");
      const source = await response.text();
      content.innerHTML = markdown(source, path) + renderAdjacent(path);
      currentPath = path;
      crumb.textContent = path.replace(/\.md$/, "").replaceAll("/", " / ").toUpperCase();
      sourceLink.href = `https://github.com/sm408/sclpl-api/blob/main/${path}`;
      toc.innerHTML = [...content.querySelectorAll("h2,h3")].map((heading) => `<a class="level-${heading.tagName.slice(1)}" href="#${heading.id}">${heading.textContent}</a>`).join("");
      addCopyButtons(content);
      renderMermaid();
      scrollToHash();
    } catch { content.innerHTML = `<h1>Page not found</h1><p>This page is not part of the published documentation bundle. Return to the <a href="docs.html">documentation index</a>.</p>`; currentPath = path; }
  };

  fetch("content/index.json").then((response) => response.json()).then((index) => {
    pages = index;
    wikiIndex = new Map(pages.map((p) => [p.path.split("/").pop().replace(/\.md$/i, "").toLowerCase(), p]));
    rebuildFlatOrder();
    renderNav(); open();
  }).catch(() => { nav.innerHTML = "<p class=loading>Documentation index unavailable. Build the site before previewing it.</p>"; });

  search.addEventListener("input", () => renderNav(search.value));

  window.addEventListener("popstate", () => {
    if (requested() === currentPath) scrollToHash();
    else open();
  });

  // Single interceptor for every internal link on the page: left nav, TOC
  // ("on this page"), in-content cross-references, and prev/next -- so
  // navigating never triggers a full reload (which used to reset scroll
  // position and lose the left panel's place).
  document.addEventListener("click", (event) => {
    const a = event.target.closest("a");
    if (!a || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const href = a.getAttribute("href") || "";
    if (href.startsWith("#")) {
      const id = decodeURIComponent(href.slice(1));
      const target = document.getElementById(id);
      if (!target) return;
      event.preventDefault();
      history.pushState(null, "", href);
      target.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
      return;
    }
    if (a.origin === location.origin && /(^|\/)docs\.html$/.test(a.pathname) && new URLSearchParams(a.search).has("doc")) {
      event.preventDefault();
      history.pushState(null, "", a.href);
      open();
    }
  });
})();
