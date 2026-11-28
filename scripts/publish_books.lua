-- publish_books.lua - pandoc filter: join a repo's docs/ into one Texinfo book.
--
--   pandoc -f markdown -t texinfo --lua-filter publish_books.lua \
--     -M plan=PLAN.json -M images=IMGDIR /dev/null
--
-- PLAN.json (written by publish_books): {"parts": [{"name": "Manual" or "",
-- "files": [abs paths, README first]}]}. Each file is read on its own as GFM,
-- so its heading ids are the GitHub ones and stay unique once prefixed.
-- Headings become raw @node/@chapter... lines (unique node names), a link to
-- another book file becomes @ref to its anchor, images are copied into
-- IMGDIR, and the GitHub-only prev/next footers and Contents lists go.
-- Any link or image that should resolve and does not stops the build.

local P = pandoc.path
local stringify = pandoc.utils.stringify

local plan, imgdir
local book = {}       -- abs path -> {prefix=, ids={}, chapter=}
local used_nodes = {}
local nimg = 0

local function fail(msg) error("publish_books: " .. msg, 0) end

local function tex(s)  -- escape text for Texinfo
  return (s:gsub("[@{}]", "@%0"))
end

local function node_name(s)
  s = s:gsub("[,:%.%(%)]", " "):gsub("%s+", " "):gsub("^ ", ""):gsub(" $", "")
  if s == "" then s = "Section" end
  local base, n = s, 1
  while used_nodes[s] do n = n + 1; s = base .. " " .. n end
  used_nodes[s] = true
  return s
end

local function read(path)
  local f = io.open(path, "r")
  if not f then fail("cannot read " .. path) end
  local t = f:read("a"); f:close()
  return pandoc.read(t, "gfm")
end

local function anchor(prefix, id) return prefix .. "-" .. id end

-- A footer like "Previous: X | Contents | Next: Y", or "[← Back]".
local function is_nav(b)
  if b.t ~= "Para" and b.t ~= "Plain" then return false end
  local has_link = false
  for _, il in ipairs(b.content) do if il.t == "Link" then has_link = true end end
  if not has_link then return false end
  local s = stringify(b)
  return s:match("^%s*Previous") or s:match("^%s*Next") or s:match("^%s*Prev")
      or s:match("^%s*←") or s:match("^%s*%[?←") or s:match("^%s*Back to")
      or s:match("^%s*Contents") or s:match("^%s*Up:")
end

local function strip(blocks, is_readme)
  local out, skip_level = {}, nil
  for i, b in ipairs(blocks) do
    if skip_level and b.t == "Header" and b.level <= skip_level then skip_level = nil end
    if not skip_level then
      if is_readme and b.t == "Header" and b.level > 1
          and (stringify(b):match("^Contents$") or stringify(b):match("^Chapters$")) then
        skip_level = b.level
      elseif is_nav(b) then
        if #out > 0 and out[#out].t == "HorizontalRule" then table.remove(out) end
      else
        out[#out + 1] = b
      end
    end
  end
  while #out > 0 and out[#out].t == "HorizontalRule" do table.remove(out) end
  return out
end

local function resolve(from, target)
  local path, frag = target:match("^([^#]*)#?(.*)$")
  if path == "" then return from, frag end
  path = path:gsub("%%20", " ")
  local parts = {}
  for seg in (P.directory(from) .. "/" .. path):gmatch("[^/]+") do
    if seg == ".." then table.remove(parts)
    elseif seg ~= "." then parts[#parts + 1] = seg end
  end
  return "/" .. table.concat(parts, "/"), frag
end

local function fix_inlines(file, inl)
  return inl:walk({
    Link = function(l)
      local t = l.target
      if t:match("^%a[%w+.-]*:") then return nil end  -- http:, mailto: ...
      local text = stringify(l.content)
      if t:match("^~") or t:match("^/") then return pandoc.Code(text ~= "" and text or t) end
      local path, frag = resolve(file, t)
      local entry = book[path]
      if not entry then
        if path:match("%.md$") and path:find(plan.docs, 1, true) == 1 then
          fail(file .. ": link to " .. t .. ": not a book chapter")
        end
        return pandoc.Span(l.content)  -- code, AGENTS.md ...: plain text
      end
      local id
      if frag == "" then id = entry.first
      else
        frag = frag:lower()
        if not entry.ids[frag] then fail(file .. ": link to " .. t .. ": no such heading") end
        id = anchor(entry.prefix, frag)
      end
      return pandoc.RawInline("texinfo", "@ref{" .. id .. ",," .. tex(text) .. "}")
    end,
    Image = function(img)
      local s = img.src
      if s:match("^%a[%w+.-]*:") then return nil end
      local path = resolve(file, s)
      local f = io.open(path, "rb")
      if not f then fail(file .. ": image " .. s .. " not found") end
      local data = f:read("a"); f:close()
      nimg = nimg + 1
      local name = string.format("%03d_%s", nimg, P.filename(path):gsub("[^%w%._-]", "_"))
      local o = io.open(P.join({ imgdir, name }), "wb"); o:write(data); o:close()
      img.src = "img/" .. name
      return img
    end,
  })
end

-- Diagram code blocks are drawn to SVG; a cache keyed by the source's hash
-- keeps a rebuild from drawing them again.
local RENDER = {
  mermaid = function(src, out) return { "mmdc", "-q", "-b", "white", "-i", src, "-o", out } end,
  d2 = function(src, out) return { "d2", src, out } end,
  dot = function(src, out) return { "dot", "-Tsvg", src, "-o", out } end,
}
RENDER.graphviz = RENDER.dot

local function diagram(file, b)
  local kind = b.classes[1]
  local render = kind and RENDER[kind]
  if not render then return nil end
  local cache = stringify(plan.cache)
  local key = pandoc.utils.sha1(kind .. "\0" .. b.text)
  local svg = P.join({ cache, key .. ".svg" })
  local f = io.open(svg, "rb")
  if not f then
    local src = P.join({ cache, key .. "." .. kind })
    local o = io.open(src, "w"); o:write(b.text); o:close()
    local cmd = render(src, svg)
    local ok, err = pcall(pandoc.pipe, cmd[1], { table.unpack(cmd, 2) }, "")
    f = io.open(svg, "rb")
    if not ok or not f then
      fail(file .. ": cannot draw the " .. kind .. " diagram: " .. tostring(err))
    end
  end
  local data = f:read("a"); f:close()
  nimg = nimg + 1
  local name = string.format("%03d_%s.svg", nimg, kind)
  local o = io.open(P.join({ imgdir, name }), "wb"); o:write(data); o:close()
  return pandoc.Para({ pandoc.Image({ pandoc.Str(kind .. " diagram") }, "img/" .. name) })
end

local CMD = { "@chapter", "@section", "@subsection", "@subsubsection" }

local function convert(file, blocks, out, min_level)
  local entry = book[file]
  for _, b in ipairs(blocks) do
    if b.t == "Header" then
      local level = b.level - min_level + 1
      local text = stringify(b.content)
      -- "2. How it works", "03 Export", "Chapter 4. The app": the book numbers
      -- chapters itself, so a title's own leading number goes.
      text = text:gsub("^[Cc]hapter%s+%d+[%.:]?%s+", ""):gsub("^%d+[%.:]?%s+(%S)", "%1")
      local lines = {}
      if level <= #CMD then
        lines[#lines + 1] = "@node " .. tex(node_name(text))
        lines[#lines + 1] = CMD[level] .. " " .. tex(text)
      else
        lines[#lines + 1] = "@subsubheading " .. tex(text)
      end
      lines[#lines + 1] = "@anchor{" .. anchor(entry.prefix, b.identifier) .. "}"
      out[#out + 1] = pandoc.RawBlock("texinfo", table.concat(lines, "\n"))
    elseif b.t == "CodeBlock" and b.classes[1] and RENDER[b.classes[1]] then
      out[#out + 1] = diagram(file, b)
    else
      out[#out + 1] = b:walk({
        CodeBlock = function(cb) return diagram(file, cb) end,
        Inlines = function(inl) return fix_inlines(file, inl) end,
      })
    end
  end
end

function Pandoc(doc)
  local f = io.open(stringify(doc.meta.plan), "r")
  plan = pandoc.json.decode(f:read("a")); f:close()
  imgdir = stringify(doc.meta.images)

  -- Pass 1: read every file, collect its heading ids.
  local docs, k = {}, 0
  for _, part in ipairs(plan.parts) do
    for _, file in ipairs(part.files) do
      k = k + 1
      local d = read(file)
      local blocks = strip(d.blocks, P.filename(file) == "README.md")
      local e = { prefix = "c" .. k, ids = {}, content = 0 }
      for _, b in ipairs(blocks) do
        if b.t == "Header" then
          e.ids[b.identifier] = true
          e.first = e.first or anchor(e.prefix, b.identifier)
        else
          e.content = e.content + 1
        end
      end
      if e.content > 0 and not e.first then  -- no heading: name it after the file
        local name = P.split_extension(P.filename(file))
        table.insert(blocks, 1, pandoc.Header(1, name, { name }))
        e.first, e.ids[name] = anchor(e.prefix, name), true
      end
      book[file] = e
      docs[file] = blocks
    end
  end

  -- A README that held only its contents list is skipped: links to it go to
  -- the next chapter of its part.
  for _, part in ipairs(plan.parts) do
    for i, file in ipairs(part.files) do
      local e = book[file]
      if e.content == 0 then
        local nxt = part.files[i + 1]
        if not nxt then fail(file .. ": a part with no chapters") end
        e.redirect = nxt
      end
    end
    for i = #part.files, 1, -1 do
      local e = book[part.files[i]]
      if e.redirect then
        local n = book[e.redirect]
        e.first, e.ids = n.first, {}
      end
    end
  end

  -- Pass 2: write the book.
  local out = {}
  for _, part in ipairs(plan.parts) do
    if part.name ~= "" then
      out[#out + 1] = pandoc.RawBlock("texinfo", "@part " .. tex(part.name))
    end
    for _, file in ipairs(part.files) do
      local blocks = docs[file]
      local min_level = 6
      for _, b in ipairs(blocks) do
        if b.t == "Header" then min_level = math.min(min_level, b.level) end
      end
      if book[file].content > 0 then
        convert(file, blocks, out, min_level)
      end
    end
  end
  return pandoc.Pandoc(out, doc.meta)
end
