-- Pandoc filter that maps the house style's Markdown conventions (EDITORIAL.md)
-- onto the theme's LaTeX components (theme.tex). Headings arrive already shifted
-- by the build script: H1 = chapter opener (or a part such as "Reference"),
-- H2 = section or standalone page, H3 = heading inside a section, H4 = sub-heading.

local function latex(inlines)
  return pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), 'latex'):gsub('%s+$', '')
end

local function raw(s) return pandoc.RawBlock('latex', s) end
local function rawi(s) return pandoc.RawInline('latex', s) end

local function from(list, i)
  local out = pandoc.List()
  for j = i, #list do out:insert(list[j]) end
  return out
end

-- Drop leading inlines up to and including the Str `word`, then any spaces.
local function after_word(inlines, word)
  local inl = pandoc.List(inlines)
  while inl[1] and not (inl[1].t == 'Str' and inl[1].text == word) do inl:remove(1) end
  inl:remove(1)
  while inl[1] and (inl[1].t == 'Space' or inl[1].t == 'SoftBreak') do inl:remove(1) end
  return inl
end

local function strip_links(inlines)
  return pandoc.Inlines(inlines):walk({ Link = function(l) return l.content end })
end

-- Chapter-end pages: inside a chapter, but not numbered as sections.
local CHAPTER_END = {
  ['Exercises and Further Reading'] = true,
  ['Questions and Sources'] = true,
  ['Problems and Further Reading'] = true,
  ['Further Reading'] = true,       -- a problem book's chapter with no problems
}

-- Problem sets (EDITORIAL.md, "Problem Sets"): problems on the chapter-end page,
-- hints and solutions in parts of their own at the back of the book.
local PROBLEM_PAGE = 'Problems and Further Reading'
local ANSWER_PARTS = { Hints = 'hints', Solutions = 'solutions' }
local DIFFICULTY = { Easy = 1, Medium = 2, Hard = 3 }
local PROBLEM_NUMBER = '^(%d+%.%d+)%s+(.+)$'
local BOOK_PART = '^Part%s+([IVXLC]+)%s+—%s+(.+)$'

-- Code blocks -----------------------------------------------------------------

local LABELS = {
  js = 'JavaScript', javascript = 'JavaScript', mjs = 'JavaScript', cjs = 'JavaScript',
  ts = 'TypeScript', typescript = 'TypeScript', json = 'JSON', jsonc = 'JSON',
  bash = 'Terminal', sh = 'Terminal', shell = 'Terminal', console = 'Terminal',
  powershell = 'PowerShell', text = '', output = 'Output', yaml = 'YAML', yml = 'YAML',
  sql = 'SQL', html = 'HTML', css = 'CSS', dockerfile = 'Dockerfile',
  graphql = 'GraphQL', ini = 'Config', toml = 'TOML', diff = 'Diff', http = 'HTTP',
  python = 'Python', go = 'Go', rust = 'Rust', java = 'Java', xml = 'XML',
}
local PLAIN = { [''] = true, text = true, output = true }
local NEUTRAL = { [''] = true, text = true, output = true, bash = true, sh = true,
                  shell = true, console = true, powershell = true }
-- A first-line comment naming a file becomes the listing's title.
local TITLE_COMMENT = { js = '//', ts = '//', jsx = '//', tsx = '//',
                        javascript = '//', typescript = '//',
                        mjs = '//', cjs = '//', bash = '#', sh = '#', yaml = '#',
                        yml = '#', dockerfile = '#', python = '#', go = '//',
                        rust = '//', java = '//', sql = '%-%-', ini = '#', toml = '#' }

local function escape_verbatim(s)
  return (s:gsub('[\\{}]', { ['\\'] = '\\textbackslash{}', ['{'] = '\\{', ['}'] = '\\}' }))
end
local function escape_text(s)
  return (s:gsub('[\\{}_%%#&%$%^~]', function(c)
    if c == '\\' then return '\\textbackslash{}' end
    if c == '^' then return '\\^{}' end
    if c == '~' then return '\\~{}' end
    return '\\' .. c
  end))
end

-- Characters the code font lacks: drawn from the symbol font, or replaced
-- with a look-alike the code font has.
local SYMBOLS = { ['✔'] = true, ['✖'] = true, ['ℹ'] = true, ['✓'] = true, ['✗'] = true }
local LOOKALIKE = { ['﹣'] = '-' }

local function with_symbols(verbatim)
  verbatim = verbatim:gsub('﹣', LOOKALIKE['﹣'])
  for sym in pairs(SYMBOLS) do
    verbatim = verbatim:gsub(sym, '\\GuideSym{' .. sym .. '}')
  end
  return verbatim
end

local function has_symbols(text)
  for sym in pairs(SYMBOLS) do
    if text:find(sym, 1, true) then return true end
  end
  return text:find('﹣', 1, true) ~= nil
end

local function code_block(el, label_override)
  local lang = el.classes[1] or ''
  local label = label_override or LABELS[lang] or (lang ~= '' and lang:upper() or '')
  local env = NEUTRAL[lang] and 'GuideOutput' or 'GuideCode'
  local title = ''
  local marker = TITLE_COMMENT[lang]
  if marker then
    -- An executable script keeps its shebang; the name comment may follow it.
    local shebang, text = '', el.text
    if text:match('^#!') then
      shebang, text = text:match('^([^\n]*\n)(.*)$')
      text = text or ''
    end
    local first, rest = text:match('^([^\n]*)\n?(.*)$')
    local name = first:match('^' .. marker .. '%s*([%w%._%-/]+%.[%w]+)%s*$')
      or first:match('^' .. marker .. '%s*(%.[%w%._%-]+)%s*$') -- dotfiles: # .env
    if name then
      title = '\\GuideOrigTexttt{' .. escape_text(name) .. '}'
      el.text = (shebang or '') .. (rest:gsub('^\n+', ''))
    end
  end
  local body = el
  -- Plain text, and any block with symbols the code font lacks, is set by hand
  -- in the same wrapping Verbatim environment the highlighter uses.
  if PLAIN[lang] or has_symbols(el.text) then
    body = raw('\\begin{Highlighting}[]\n' .. with_symbols(escape_verbatim(el.text))
               .. '\n\\end{Highlighting}')
  end
  if title ~= '' then
    env = env .. 'Titled'
    return { raw(string.format('\\begin{%s}{%s}{%s}', env, label, title)), body,
             raw('\\end{' .. env .. '}') }
  end
  return { raw(string.format('\\begin{%s}{%s}', env, label)), body, raw('\\end{' .. env .. '}') }
end

-- Callouts --------------------------------------------------------------------

local CALLOUTS = {
  ['Note:'] = { 'NoteInk', 'NoteTint', 'Note' },
  ['Tip:'] = { 'AccentDark', 'AccentTint', 'Tip' },
  ['Warning:'] = { 'WarnInk', 'WarnTint', 'Warning' },
}

local function block_quote(el)
  local first = el.content[1]
  if first and first.t == 'Para' and first.content[1] and first.content[1].t == 'Strong' then
    local style = CALLOUTS[pandoc.utils.stringify(first.content[1])]
    if style then
      local rest = from(first.content, 2)
      while rest[1] and (rest[1].t == 'Space' or rest[1].t == 'SoftBreak') do rest:remove(1) end
      return pandoc.List({ raw(string.format('\\begin{GuideCallout}{%s}{%s}{%s}',
                                             style[1], style[2], style[3])),
                           pandoc.Para(rest) })
        :extend(from(el.content, 2)):extend({ raw('\\end{GuideCallout}') })
    end
  end
  -- A quote that opens with kana or kanji is an example sentence in a
  -- language-learning book (EDITORIAL.md, "Language-learning books").
  local opening = first and pandoc.utils.stringify(first) or ''
  if opening:find('^[\227-\233]') then
    return pandoc.List({ raw('\\begin{GuideExample}') }):extend(el.content)
      :extend({ raw('\\end{GuideExample}') })
  end
  return pandoc.List({ raw('\\begin{GuideQuote}') }):extend(el.content)
    :extend({ raw('\\end{GuideQuote}') })
end

-- Figures ---------------------------------------------------------------------

local function is_image_block(b)
  if b.t == 'Figure' then return true end
  return b.t == 'Para' and #b.content == 1 and b.content[1].t == 'Image'
end

-- `*Figure: text*` right after an image: returns the caption inlines.
local function figure_caption(b)
  if not b or b.t ~= 'Para' or #b.content ~= 1 or b.content[1].t ~= 'Emph' then return nil end
  local inl = b.content[1].content
  if not (inl[1] and inl[1].t == 'Str' and inl[1].text == 'Figure:') then return nil end
  return after_word(inl, 'Figure:')
end

local function image_para(b)
  if b.t == 'Figure' then
    local imgs = pandoc.List()
    b:walk({ Image = function(img) imgs:insert(img) end })
    return pandoc.Para(imgs)
  end
  return b
end

-- Links: URL footnotes and numbered cross-references --------------------------

local numbers = {}   -- anchor id -> { kind = 'section' | 'chapter', n = '1.3' }

local function link(el)
  local target = el.target
  if target:match('^https?://') then
    local text = pandoc.utils.stringify(el.content)
    if text == target or text == target:gsub('^https?://', '') then return el end
    local url = target:gsub('\\', '\\textbackslash{}'):gsub('#', '\\#'):gsub('%%', '\\%%')
    return { el, rawi('\\footnote{\\url{' .. url .. '}}') }
  end
  local id = target:match('^#(.+)$')
  local ref = id and numbers[id]
  if ref then
    local text = pandoc.utils.stringify(el.content):lower()
    if not (text:find('section', 1, true) or text:find('chapter', 1, true)) then
      return { el, pandoc.Str(' (' .. ref.kind .. '\u{a0}' .. ref.n .. ')') }
    end
  end
  return el
end

local function inline_filters(b)
  return b:walk({ Link = link })
end

-- Index -----------------------------------------------------------------------

local terms = {}     -- { { display = 'Event loop', keys = { 'event loop' } }, ... }

local function index_escape(s)
  s = s:gsub('(["!@|])', '"%1')   -- makeindex specials
  return escape_text(s)
end

local function add_term(strong)
  local display = pandoc.utils.stringify(strong):gsub('%s+', ' ')
  local keys = {}
  local base = display:gsub('%s*%b()', ''):gsub('^%s+', ''):gsub('%s+$', '')
  if #base > 1 then keys[#keys + 1] = base:lower() end
  for inner in display:gmatch('%(([^)]+)%)') do
    if #inner > 1 then keys[#keys + 1] = inner:lower() end
  end
  if #keys > 0 then terms[#terms + 1] = { display = display, keys = keys } end
end

local function collect_glossary(blocks, start)
  for i = start, #blocks do
    local b = blocks[i]
    if b.t == 'Header' and b.level <= 2 then break end
    if b.t == 'Para' then
      for _, inl in ipairs(b.content) do
        if inl.t == 'Strong' then add_term(inl)
        elseif inl.t == 'Str' and (inl.text == '—' or inl.text == '--') then break end
      end
    end
  end
end

local function lua_escape(s) return (s:gsub('[%^%$%(%)%%%.%[%]%*%+%-%?]', '%%%0')) end

local function has_term(text, key)
  return text:find('%f[%w]' .. lua_escape(key) .. '%f[^%w]') ~= nil
end

-- Headings --------------------------------------------------------------------

local book_parts = false   -- set in pass 1 when the book has "Part N — Title" parts

local function heading(el)
  local text = pandoc.utils.stringify(el)
  local id = el.identifier
  local content = strip_links(el.content)
  if el.level == 1 then
    if text:match('^Chapter%s+%d+%s+—%s+') then
      local n = text:match('^Chapter%s+(%d+)')
      return raw(string.format('\\GuideChapter{%s}{%s}{%s}', n, latex(after_word(content, '—')), id))
    end
    local numeral = text:match(BOOK_PART)
    if numeral then
      return raw(string.format('\\GuideBookPart{%s}{%s}{%s}{%s}', numeral,
                               latex(after_word(content, '—')), id, escape_text(text)))
    end
    if book_parts then
      return raw(string.format('\\GuideBookPart{}{%s}{%s}{%s}', latex(content), id,
                               escape_text(text)))
    end
    return raw(string.format('\\GuidePart{%s}{%s}', latex(content), id))
  elseif el.level == 2 then
    if el.classes:includes('standalone') then
      return raw(string.format('\\GuideInChapterfalse\\GuideLesson{%s}{%s}', latex(content), id))
    end
    if CHAPTER_END[text] then
      return raw(string.format('\\GuideChapterEnd{%s}{%s}', latex(content), id))
    end
    return raw(string.format('\\GuideLesson{%s}{%s}', latex(content), id))
  elseif el.level == 4 and text:match('^%u$') then
    return raw(string.format('\\GuideGlossaryLetter{%s}', text))  -- glossary "### A"
  end
  el.content = content
  return el
end

-- Problem sets ----------------------------------------------------------------

-- The heading's inlines without the leading problem number ("5.2").
local function after_number(inlines)
  local inl = pandoc.List(inlines)
  inl:remove(1)
  while inl[1] and (inl[1].t == 'Space' or inl[1].t == 'SoftBreak') do inl:remove(1) end
  return inl
end

-- `**Medium** · Target: O(n) time, O(1) space` -> 'Medium', target inlines.
local function problem_meta(b)
  if not b or b.t ~= 'Para' or not b.content[1] or b.content[1].t ~= 'Strong' then return nil end
  local difficulty = pandoc.utils.stringify(b.content[1])
  if not DIFFICULTY[difficulty] then return nil end
  local target, started = pandoc.List(), false
  for _, inl in ipairs(from(b.content, 2)) do
    if started then
      target:insert(inl)
    elseif inl.t == 'Str' and inl.text == 'Target:' then
      started = true
    elseif inl.t == 'Str' and inl.text ~= '·' then
      started = true
      target:insert(inl)
    end
  end
  while target[1] and (target[1].t == 'Space' or target[1].t == 'SoftBreak') do target:remove(1) end
  return difficulty, target
end

-- About how many body lines a problem takes, from its heading to the next
-- heading, so a problem that fits on a page is never split across two.
local function problem_height(blocks, i)
  local lines = 5                                   -- rule, label, title, signatures
  for j = i + 1, #blocks do
    local b = blocks[j]
    if b.t == 'Header' then break end
    if b.t == 'CodeBlock' then
      lines = lines + (select(2, b.text:gsub('\n', '')) + 1) * 0.8 + 1.2
    elseif b.t == 'Para' or b.t == 'Plain' then
      lines = lines + math.ceil(#pandoc.utils.stringify(b) / 95) + 0.5
    elseif b.t == 'BulletList' or b.t == 'OrderedList' then
      for _, item in ipairs(b.content) do
        lines = lines + math.ceil(#pandoc.utils.stringify(item) / 90)
      end
    end
  end
  return math.ceil(lines)
end

-- A paragraph of nothing but inline code separated by `·`: the signatures.
local function signatures(b)
  if not b or b.t ~= 'Para' then return nil end
  local has_code = false
  for _, inl in ipairs(b.content) do
    if inl.t == 'Code' then
      has_code = true
    elseif not (inl.t == 'Space' or inl.t == 'SoftBreak' or (inl.t == 'Str' and inl.text == '·')) then
      return nil
    end
  end
  if not has_code then return nil end
  return (latex(b.content):gsub('%s*·%s*', '{\\color{Faint}\\enspace·\\enspace}'))
end

local function is_label_para(b, word)
  return b.t == 'Para' and #b.content == 1 and b.content[1].t == 'Strong'
    and pandoc.utils.stringify(b.content[1]) == word
end

-- `**Brute force.** …` in a solution: the lead-in becomes a run-in label.
local function run_in(b)
  local first = b.content[1]
  if b.t ~= 'Para' or not first or first.t ~= 'Strong' then return b end
  if not pandoc.utils.stringify(first):match('%.$') then return b end
  local content = pandoc.List({ rawi('\\GuideRunIn{' .. latex(first.content) .. '}') })
  return pandoc.Para(content:extend(from(b.content, 2)))
end

-- The document ----------------------------------------------------------------

function Pandoc(doc)
  local blocks = doc.blocks

  -- Pass 1: section and chapter numbers for cross-references; glossary terms;
  -- which problems have a hint and a solution.
  local chapter, lesson, in_chapter = nil, 0, false
  local answers = { hints = {}, solutions = {} }
  local part_mode = nil
  for i, b in ipairs(blocks) do
    if b.t == 'Header' then
      local text = pandoc.utils.stringify(b)
      if b.level == 1 then
        if text:match(BOOK_PART) then book_parts = true end
        part_mode = ANSWER_PARTS[text]
      elseif b.level == 3 and part_mode then
        local n = text:match(PROBLEM_NUMBER)
        if n then answers[part_mode][n] = true end
      end
      if b.level == 1 then
        chapter = text:match('^Chapter%s+(%d+)%s+—%s+')
        lesson, in_chapter = 0, chapter ~= nil
        if chapter then numbers[b.identifier] = { kind = 'chapter', n = chapter } end
      elseif b.level == 2 then
        if b.classes:includes('standalone') then in_chapter = false end
        if in_chapter and not CHAPTER_END[text] then
          lesson = lesson + 1
          numbers[b.identifier] = { kind = 'section', n = chapter .. '.' .. lesson }
        end
        if text == 'Glossary' then collect_glossary(blocks, i + 1) end
      end
    end
  end

  -- Pass 2: build the output.
  local out = pandoc.List()
  local open, open_level = nil, nil   -- the open Summary panel or sidebar
  local indexed = {}                  -- terms already indexed in this section
  local in_glossary = false

  local function close(level)
    if open and (level == nil or level <= open_level) then
      out:insert(raw('\\end{' .. open .. '}'))
      open, open_level = nil, nil
    end
  end

  -- The problem being set, closed with its hint and solution page references.
  local problem = nil
  local keep_listings = next(answers.hints) ~= nil or next(answers.solutions) ~= nil
  part_mode = nil
  local page_mode = nil
  local function close_problem()
    if problem then
      out:insert(raw(string.format('\\GuideProblemEnd{%s}{%d}{%d}', problem,
        answers.hints[problem] and 1 or 0, answers.solutions[problem] and 1 or 0)))
      problem = nil
    end
  end

  local function index_para(b)
    if in_glossary or #terms == 0 then return b end
    local text = pandoc.utils.stringify(b):lower()
    local marks = pandoc.List()
    for _, t in ipairs(terms) do
      if not indexed[t.display] then
        for _, key in ipairs(t.keys) do
          if has_term(text, key) then
            indexed[t.display] = true
            marks:insert(rawi('\\index{' .. index_escape(t.display:lower()) .. '@'
                              .. index_escape(t.display) .. '}'))
            break
          end
        end
      end
    end
    if #marks == 0 then return b end
    local content = marks:extend(b.content)
    return b.t == 'Para' and pandoc.Para(content) or pandoc.Plain(content)
  end

  local function list_block(b)
    local items = pandoc.List()
    for _, item in ipairs(b.content) do
      local inner = pandoc.List()
      for _, ib in ipairs(item) do
        if ib.t == 'Para' or ib.t == 'Plain' then ib = index_para(ib) end
        inner:insert(inline_filters(ib))
      end
      items:insert(inner)
    end
    if b.t == 'BulletList' then return pandoc.BulletList(items) end
    return pandoc.OrderedList(items, b.listAttributes)
  end

  local i = 1
  while i <= #blocks do
    local b = blocks[i]
    local step = 1
    if b.t == 'Header' then
      local text = pandoc.utils.stringify(b)
      close(b.level)
      close_problem()
      if b.level <= 2 then
        indexed = {}
        in_glossary = (b.level == 2 and text == 'Glossary')
      end
      if b.level == 1 then
        part_mode, page_mode = ANSWER_PARTS[text], nil
      elseif b.level == 2 then
        page_mode = (text == PROBLEM_PAGE) and 'problems' or nil
      end
      local number = text:match(PROBLEM_NUMBER)
      local chapter_n = text:match('^Chapter%s+(%d+)%s+—%s+')
      if b.level == 2 and part_mode and chapter_n then
        out:insert(raw(string.format('\\GuideAnswerPage{%s}{%s}{%s}{%s}{%d}',
          part_mode == 'hints' and 'Hints' or 'Solutions', chapter_n,
          latex(after_word(strip_links(b.content), '—')), b.identifier,
          part_mode == 'solutions' and 1 or 0)))
      elseif b.level == 3 and part_mode and number then
        local macro = part_mode == 'hints' and 'GuideHint' or 'GuideSolution'
        out:insert(raw(string.format('\\%s{%s}{%s}', macro, number,
          latex(after_number(strip_links(b.content))))))
      elseif b.level == 4 and page_mode == 'problems' and number then
        local difficulty, target = problem_meta(blocks[i + 1])
        local sigs = signatures(blocks[i + (difficulty and 2 or 1)])
        local height = problem_height(blocks, i)
        if height <= 36 then
          out:insert(raw(string.format('\\par\\Needspace*{%d\\baselineskip}', height)))
        end
        out:insert(raw(string.format('\\GuideProblem{%s}{%s}{%d}{%s}{%s}{%s}', number,
          latex(after_number(strip_links(b.content))), DIFFICULTY[difficulty] or 0,
          difficulty or '', target and latex(target) or '', sigs or '')))
        step = 1 + (difficulty and 1 or 0) + (sigs and 1 or 0)
        problem = number
      elseif b.level == 3 and page_mode == 'problems' and text == 'Problems' then
        -- The heading travels with the first problem instead of ending a page.
        local nxt = blocks[i + 1]
        if nxt and nxt.t == 'Header' and pandoc.utils.stringify(nxt):match(PROBLEM_NUMBER) then
          local height = problem_height(blocks, i + 1)
          if height <= 32 then
            out:insert(raw(string.format('\\par\\Needspace*{%d\\baselineskip}', height + 4)))
          end
        end
        out:insert(heading(b))
      elseif b.level == 3 and text == 'Summary' then
        -- In a problem book a summary panel, like a listing, stays in one piece.
        out:insert(raw((keep_listings and '\\GuideKeepListingtrue' or '') .. '\\begin{GuideSummary}'
                       .. (keep_listings and '\\GuideKeepListingfalse' or '')))
        open, open_level = 'GuideSummary', 3
      elseif b.level == 4 and text:match('^Going [Dd]eeper:') then
        local word = text:match('^Going ([Dd]eeper:)')
        local title = latex(strip_links(after_word(b.content, word)))
        out:insert(raw('\\phantomsection\\hypertarget{' .. b.identifier .. '}{}'
                       .. '\\begin{GuideSidebar}{' .. title .. '}'))
        open, open_level = 'GuideSidebar', 4
      else
        out:insert(heading(b))
      end
    elseif is_image_block(b) then
      local caption = figure_caption(blocks[i + 1])
      if caption then
        out:extend({ raw('\\begin{GuideFigure}'), image_para(b),
                     raw('\\GuideCaption{' .. latex(caption) .. '}'), raw('\\end{GuideFigure}') })
        step = 2
      else
        out:insert(image_para(b))
      end
    elseif b.t == 'CodeBlock' then
      -- In a problem book, a listing short enough to fit on a page is never
      -- split across two: code read across a page turn is code misread.
      local keep = keep_listings and select(2, b.text:gsub('\n', '')) < 30
      local examples = problem and b.text:match('^Input:')
      if keep then out:insert(raw('\\GuideKeepListingtrue')) end
      out:extend(code_block(b, examples and 'Examples' or nil))
      if keep then out:insert(raw('\\GuideKeepListingfalse')) end
    elseif problem and is_label_para(b, 'Constraints') then
      out:insert(raw('\\GuideProblemLabel{Constraints}'))
    elseif part_mode == 'solutions' and b.t == 'Para' then
      -- A lead-in on its own ("Common mistakes.") stays with what follows it.
      if #b.content == 1 and b.content[1].t == 'Strong' then
        out:insert(raw('\\par\\Needspace*{4\\baselineskip}'))
      end
      out:insert(inline_filters(index_para(run_in(b))))
    elseif b.t == 'BlockQuote' then
      out:extend(block_quote(inline_filters(b)))
    elseif b.t == 'Table' then
      out:extend({ raw('\\begingroup\\GuideTableSetup'), inline_filters(b), raw('\\endgroup') })
    elseif b.t == 'HorizontalRule' then
      -- a web convention; the book uses space instead
    elseif b.t == 'Para' or b.t == 'Plain' then
      out:insert(inline_filters(index_para(b)))
    elseif b.t == 'BulletList' or b.t == 'OrderedList' then
      out:insert(list_block(b))
    else
      out:insert(inline_filters(b))
    end
    i = i + step
  end
  close()
  close_problem()
  if #terms > 0 then out:insert(raw('\\GuideIndex')) end
  out:insert(raw('\\GuideBackCover'))
  doc.blocks = out
  return doc
end

return { { Pandoc = Pandoc } }
