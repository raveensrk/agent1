-- publish.lua - pandoc filter: model_and_harness.yaml becomes the shared page.
--
--   pandoc -f markdown -t html5 -s --embed-resources --css publish.css \
--     --metadata-file model_and_harness.yaml --lua-filter publish.lua /dev/null
--
-- The YAML arrives as metadata. This filter writes the page as pandoc markdown
-- (fenced divs carry the outline-N classes publish.css styles) and reads it
-- back: a title, a table of contents, the shared rating scale, then Models and
-- Harness, each with its recommendations and one boxed review per entry,
-- headed `Name - version V - effort E - rating R/10 - DATE`, tag as a pill.
-- `rules` fields stay out of the page.

local stringify = pandoc.utils.stringify
local TITLE = "Models & Harness Reviews"

-- A metadata value back to markdown text, links and paragraphs intact.
local function md(value)
  local kind = pandoc.utils.type(value)
  if kind == "Inlines" then
    value = pandoc.Blocks({pandoc.Plain(value)})
  elseif kind ~= "Blocks" then
    return stringify(value)
  end
  return (pandoc.write(pandoc.Pandoc(value), "markdown"):gsub("%s+$", ""))
end

-- `1: Pi` keys arrive as strings; sort them as numbers so 10 follows 9.
local function ranked(map)
  local keys = {}
  for key in pairs(map or {}) do table.insert(keys, key) end
  table.sort(keys, function(a, b) return tonumber(a) < tonumber(b) end)
  local values = {}
  for _, key in ipairs(keys) do table.insert(values, map[key]) end
  return values
end

local function numbered(lines)
  for i, line in ipairs(lines) do lines[i] = i .. ". " .. line end
  return table.concat(lines, "\n")
end

local page, toc = {}, {}

local function add(text) table.insert(page, text) end

-- Open a section; levels 2 and 3 are listed in the table of contents.
local function open(level, text, id)
  if level <= 3 then table.insert(toc, {level = level, text = text, id = id}) end
  add(string.format("::: {.outline-%d}", level))
  add(string.format("%s %s {#%s}", string.rep("#", level), text, id))
end

local function close() add(":::") end

local function review_heading(r)
  local fields = {stringify(r.name)}
  if r.version then table.insert(fields, "version " .. stringify(r.version)) end
  if r.effort then table.insert(fields, "effort " .. stringify(r.effort)) end
  local rating = stringify(r.rating)
  if rating ~= "unrated" then rating = rating .. "/10" end
  table.insert(fields, "rating " .. rating)
  table.insert(fields, stringify(r.date))
  local heading = "#### " .. table.concat(fields, " - ")
  if r.tag then heading = heading .. " [" .. stringify(r.tag) .. "]{.tag}" end
  return heading
end

local function reviews(section, prefix)
  open(3, "Reviews", prefix .. "-reviews")
  if section.intro then add(md(section.intro)) end
  for _, r in ipairs(section.reviews or {}) do
    add("::: {.outline-4}")
    add(review_heading(r))
    add(md(r.note))
    close()
  end
  close()
end

local function rating_scale(scale)
  open(2, "Rating Scale", "rating-scale")
  add(md(scale.intro))
  local rows = {"| Rating | Label | Meaning |", "|---|---|---|"}
  for _, level in ipairs(scale.levels or {}) do
    table.insert(rows, string.format("| %s/10 | %s | %s |",
      stringify(level.rating), stringify(level.label), stringify(level.meaning)))
  end
  add(table.concat(rows, "\n"))
  close()
end

local function models(m)
  open(2, "Models", "models")
  local rec = m.recommendations
  open(3, "Recommendations", "models-recommendations")
  add(md(rec.intro))
  local sources = {}
  for _, source in ipairs(rec.sources or {}) do
    table.insert(sources, "- " .. md(source))
  end
  add("Reference sources for recommendations:\n\n" .. table.concat(sources, "\n"))
  for _, tier in ipairs(rec.tiers or {}) do
    local name = stringify(tier.tier)
    add("::: {.outline-4}")
    add("#### " .. name .. " {#models-" .. name:lower() .. "}")
    local picks = {}
    for _, pick in ipairs(ranked(tier.picks)) do
      table.insert(picks, stringify(pick.name) .. " (" .. stringify(pick.effort) .. " effort)")
    end
    add(numbered(picks))
    close()
  end
  close()
  reviews(m, "models")
  close()
end

local function harnesses(h)
  open(2, "Harness", "harness")
  open(3, "Recommendations", "harness-recommendations")
  local picks = {}
  for _, name in ipairs(ranked(h.recommendations)) do table.insert(picks, stringify(name)) end
  add(numbered(picks))
  close()
  reviews(h, "harness")
  close()
end

local function contents()
  local lines = {}
  for _, entry in ipairs(toc) do
    local indent = string.rep("    ", entry.level - 2)
    table.insert(lines, string.format("%s- [%s](#%s)", indent, entry.text, entry.id))
  end
  -- Raw HTML for the box and its heading: pandoc turns a div that opens with a
  -- markdown heading into a section and moves the div's id onto it.
  return '<div id="table-of-contents">\n<h2>Table of Contents</h2>\n\n'
    .. "::: {#text-table-of-contents}\n" .. table.concat(lines, "\n") .. "\n:::\n\n</div>"
end

function Pandoc(doc)
  local m = doc.meta
  rating_scale(m.rating_scale)
  models(m.models)
  harnesses(m.harnesses)
  local body = table.concat({
    "::: {#content}",
    "# " .. TITLE .. " {.title}",
    contents(),
    table.concat(page, "\n\n"),
    ":::",
  }, "\n\n")
  local out = pandoc.read(body, "markdown")
  out.meta = pandoc.Meta({pagetitle = TITLE})
  return out
end
