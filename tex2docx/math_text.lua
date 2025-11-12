--[[
Inline math normalizer - promote textual formulas to styled text

This filter targets inline math segments that actually represent textual
content such as chemical formulas (e.g. CO_{2}) or units (e.g. m^{3}).
Pandoc would otherwise emit Word OMML runs that render alphabetic symbols
in italics. The filter rewrites these simple math fragments into regular
inlines that use superscript and subscript markup so the resulting DOCX
keeps upright glyphs.
]]

local markdown_reader = 'markdown+superscript+subscript'

local TEXT_COMMANDS = {
  mathrm = true,
  text = true,
  textrm = true,
  textnormal = true,
  operatorname = true,
  mbox = true,
}

local WHITESPACE_COMMANDS = {
  [' '] = true,
  quad = true,
  qquad = true,
  thinspace = true,
  negthinspace = true,
  negmedspace = true,
  negthickspace = true,
}

local SINGLE_CHAR_COMMANDS = {
  [' '] = ' ',
  [','] = ' ',
  [';'] = ' ',
  [':'] = ' ',
  ['!'] = '',
  ['%'] = '%',
  ['_'] = '_',
  ['^'] = '^',
  ['-'] = '-',
}

local function is_allowed_char(ch)
  if ch:match('%w') then
    return true
  end
  if ch == ' ' then
    return true
  end
  if ch:match('[%-%+,%.%/%(%)]') then
    return true
  end
  if ch == '[' or ch == ']' then
    return true
  end
  if ch == ':' or ch == ';' then
    return true
  end
  if ch == "'" or ch == '"' then
    return true
  end
  if ch == '·' or ch == '·' then
    return true
  end
  if ch == '~' then
    return true
  end
  return false
end

local function read_group(text, start_index)
  local depth = 0
  local i = start_index
  local len = #text
  while i <= len do
    local ch = text:sub(i, i)
    if ch == '{' then
      depth = depth + 1
    elseif ch == '}' then
      depth = depth - 1
      if depth == 0 then
        local content = text:sub(start_index + 1, i - 1)
        return content, i + 1
      end
    elseif ch == '\\' then
      i = i + 1
    end
    i = i + 1
  end
  return nil, nil
end

local function sanitize_plain_text(text)
  local parts = {}
  local i = 1
  local len = #text

  while i <= len do
    local ch = text:sub(i, i)

    if ch == '\\' then
      if i == len then
        return nil
      end
      local next_char = text:sub(i + 1, i + 1)
      if next_char:match('%a') then
        local j = i + 1
        while j <= len and text:sub(j, j):match('%a') do
          j = j + 1
        end
        local cmd = text:sub(i + 1, j - 1)
        if TEXT_COMMANDS[cmd] then
          local content, next_index = read_group(text, j)
          if not content then
            return nil
          end
          local sanitized = sanitize_plain_text(content)
          if not sanitized then
            return nil
          end
          if sanitized ~= '' then
            parts[#parts + 1] = sanitized
          end
          i = next_index
        elseif WHITESPACE_COMMANDS[cmd] then
          parts[#parts + 1] = ' '
          i = j
        elseif cmd == 'textsuperscript' or cmd == 'textsubscript' then
          return nil
        else
          return nil
        end
      else
        local mapped = SINGLE_CHAR_COMMANDS[next_char]
        if mapped == nil then
          return nil
        end
        if mapped ~= '' then
          parts[#parts + 1] = mapped
        end
        i = i + 2
      end
    elseif ch == '{' then
      local content, next_index = read_group(text, i)
      if not content then
        return nil
      end
      local sanitized = sanitize_plain_text(content)
      if not sanitized then
        return nil
      end
      if sanitized ~= '' then
        parts[#parts + 1] = sanitized
      end
      i = next_index
    elseif ch == '}' then
      return nil
    else
      if not is_allowed_char(ch) then
        return nil
      end
      parts[#parts + 1] = ch
      i = i + 1
    end
  end

  return table.concat(parts)
end

local function read_super_sub(text, index)
  if index > #text then
    return nil, nil
  end
  local ch = text:sub(index, index)
  if ch == '{' then
    return read_group(text, index)
  end
  return text:sub(index, index), index + 1
end

local function handle_command(math_text, index)
  local len = #math_text
  if index > len then
    return nil, nil
  end
  local next_char = math_text:sub(index + 1, index + 1)
  if not next_char or next_char == '' then
    return nil, nil
  end

  if next_char:match('%a') then
    local j = index + 1
    while j <= len and math_text:sub(j, j):match('%a') do
      j = j + 1
    end
    local cmd = math_text:sub(index + 1, j - 1)
    if TEXT_COMMANDS[cmd] then
      local content, next_index = read_group(math_text, j)
      if not content then
        return nil, nil
      end
      local sanitized = sanitize_plain_text(content)
      if not sanitized then
        return nil, nil
      end
      if sanitized ~= '' then
        return { kind = 'text', value = sanitized }, next_index
      end
      return { kind = 'noop' }, next_index
    elseif WHITESPACE_COMMANDS[cmd] then
      return { kind = 'text', value = ' ' }, j
    elseif cmd == 'textsuperscript' or cmd == 'textsubscript' then
      local content, next_index = read_group(math_text, j)
      if not content then
        return nil, nil
      end
      local sanitized = sanitize_plain_text(content)
      if not sanitized or sanitized == '' then
        return nil, nil
      end
      local kind = cmd == 'textsuperscript' and 'sup' or 'sub'
      return { kind = kind, value = sanitized }, next_index
    else
      return nil, nil
    end
  end

  local mapped = SINGLE_CHAR_COMMANDS[next_char]
  if mapped == nil then
    return nil, nil
  end
  if mapped == '' then
    return { kind = 'noop' }, index + 2
  end
  return { kind = 'text', value = mapped }, index + 2
end

local function parse_math_inline(expr)
  local tokens = {}
  local buffer = {}
  local len = #expr
  local i = 1

  local function flush_buffer()
    if #buffer == 0 then
      return
    end
    local combined = table.concat(buffer)
    if combined ~= '' then
      tokens[#tokens + 1] = { kind = 'text', value = combined }
    end
    buffer = {}
  end

  local function append_text(value)
    if value ~= '' then
      buffer[#buffer + 1] = value
    end
  end

  while i <= len do
    local ch = expr:sub(i, i)

    if ch == '\\' then
      local result, next_index = handle_command(expr, i)
      if not result then
        return nil
      end
      if result.kind == 'text' then
        append_text(result.value)
      elseif result.kind == 'sup' or result.kind == 'sub' then
        flush_buffer()
        tokens[#tokens + 1] = result
      end
      i = next_index
    elseif ch == '^' or ch == '_' then
      flush_buffer()
      local kind = ch == '^' and 'sup' or 'sub'
      local value, next_index = read_super_sub(expr, i + 1)
      if not value then
        return nil
      end
      local sanitized = sanitize_plain_text(value)
      if not sanitized or sanitized == '' then
        return nil
      end
      tokens[#tokens + 1] = { kind = kind, value = sanitized }
      i = next_index
    elseif ch == '{' then
      local content, next_index = read_group(expr, i)
      if not content then
        return nil
      end
      local sanitized = sanitize_plain_text(content)
      if not sanitized then
        return nil
      end
      append_text(sanitized)
      i = next_index
    elseif ch == '}' then
      return nil
    else
      if not is_allowed_char(ch) then
        return nil
      end
      append_text(ch)
      i = i + 1
    end
  end

  flush_buffer()

  if #tokens == 0 then
    return nil
  end

  local has_letter = false
  for _, token in ipairs(tokens) do
    if token.kind == 'text' and token.value:find('%a') then
      has_letter = true
      break
    end
  end

  if not has_letter then
    return nil
  end

  for _, token in ipairs(tokens) do
    if token.kind == 'text' then
      if token.value:find('%s') then
        return nil
      end
      if token.value:find('[%+=/]') then
        return nil
      end
      if token.value:find('[<>]') then
        return nil
      end
    end
  end

  return tokens
end

local function tokens_to_markdown(tokens)
  local parts = {}
  for _, token in ipairs(tokens) do
    if token.kind == 'text' then
      parts[#parts + 1] = token.value
    elseif token.kind == 'sup' then
      if token.value:find('%^') then
        return nil
      end
      parts[#parts + 1] = '^' .. token.value .. '^'
    elseif token.kind == 'sub' then
      if token.value:find('~') then
        return nil
      end
      parts[#parts + 1] = '~' .. token.value .. '~'
    end
  end
  return table.concat(parts)
end

local function convert_tokens_to_inlines(tokens)
  local markdown = tokens_to_markdown(tokens)
  if not markdown or markdown == '' then
    return nil
  end

  local ok, doc = pcall(pandoc.read, markdown, markdown_reader)
  if not ok or not doc or not doc.blocks or #doc.blocks == 0 then
    return nil
  end

  local block = doc.blocks[1]
  if block.t ~= 'Para' and block.t ~= 'Plain' then
    return nil
  end

  return block.c
end

local function transform_math(math_elem)
  if math_elem.mathtype ~= pandoc.InlineMath then
    return nil
  end

  local expr = math_elem.text
  if not expr:find('[%_%^]') then
    return nil
  end

  local tokens = parse_math_inline(expr)
  if not tokens then
    return nil
  end

  return convert_tokens_to_inlines(tokens)
end

return {
  {
    Math = transform_math,
  },
}
