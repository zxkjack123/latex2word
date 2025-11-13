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

local SIUNITX_COMMANDS = {
  SI = true,
  si = true,
  num = true,
}

local SIUNITX_PREFIXES = {
  kilo = 'k',
  mega = 'M',
  giga = 'G',
  tera = 'T',
  milli = 'm',
  micro = 'µ',
  nano = 'n',
  pico = 'p',
  femto = 'f',
  centi = 'c',
  deci = 'd',
  deca = 'da',
  hecto = 'h',
}

local SIUNITX_UNITS = {
  kelvin = 'K',
  celsius = '°C',
  fahrenheit = '°F',
  meter = 'm',
  metre = 'm',
  gram = 'g',
  kilogram = 'kg',
  second = 's',
  ampere = 'A',
  mole = 'mol',
  candela = 'cd',
  joule = 'J',
  watt = 'W',
  pascal = 'Pa',
  newton = 'N',
  volt = 'V',
  ohm = 'Ω',
  siemens = 'S',
  weber = 'Wb',
  tesla = 'T',
  henry = 'H',
  lumen = 'lm',
  lux = 'lx',
  becquerel = 'Bq',
  gray = 'Gy',
  sievert = 'Sv',
  katal = 'kat',
  coulomb = 'C',
  farad = 'F',
  liter = 'L',
  litre = 'L',
  hertz = 'Hz',
  radian = 'rad',
  steradian = 'sr',
  day = 'd',
  hour = 'h',
  minute = 'min',
  year = 'yr',
  percent = '%',
  degree = '°',
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

local SYMBOL_COMMANDS = {
  times = '×',
  cdot = '·',
  to = '→',
  rightarrow = '→',
  longrightarrow = '→',
  leftarrow = '←',
  longleftarrow = '←',
}

local GREEK_COMMANDS = {
  alpha = 'α',
  beta = 'β',
  gamma = 'γ',
  delta = 'δ',
  epsilon = 'ε',
  varepsilon = 'ε',
  zeta = 'ζ',
  eta = 'η',
  theta = 'θ',
  vartheta = 'ϑ',
  iota = 'ι',
  kappa = 'κ',
  lambda = 'λ',
  mu = 'μ',
  nu = 'ν',
  xi = 'ξ',
  pi = 'π',
  varpi = 'ϖ',
  rho = 'ρ',
  varrho = 'ϱ',
  sigma = 'σ',
  varsigma = 'ς',
  tau = 'τ',
  upsilon = 'υ',
  phi = 'φ',
  varphi = 'ϕ',
  chi = 'χ',
  psi = 'ψ',
  omega = 'ω',
  Gamma = 'Γ',
  Delta = 'Δ',
  Theta = 'Θ',
  Lambda = 'Λ',
  Xi = 'Ξ',
  Pi = 'Π',
  Sigma = 'Σ',
  Upsilon = 'Υ',
  Phi = 'Φ',
  Psi = 'Ψ',
  Omega = 'Ω',
}

local GREEK_CHAR_LOOKUP = {}
for _, char in pairs(GREEK_COMMANDS) do
  GREEK_CHAR_LOOKUP[char] = true
end

local WARNED_EXPRESSIONS = {}

local function warn_nonstandard_unit(expr)
  if WARNED_EXPRESSIONS[expr] then
    return
  end
  WARNED_EXPRESSIONS[expr] = true
  io.stderr:write(
    string.format(
      "[tex2docx] Warning: Non-standard unit expression '%s'. " ..
      "Consider using \\SI or \\num for SCI compliance.\n",
      expr
    )
  )
end

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
  if ch == '×' or ch == '→' or ch == '←' then
    return true
  end
  if ch == 'µ' or ch == 'Ω' or ch == '°' then
    return true
  end
  if ch == '~' then
    return true
  end
  if GREEK_CHAR_LOOKUP[ch] then
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
        elseif GREEK_COMMANDS[cmd] then
          parts[#parts + 1] = GREEK_COMMANDS[cmd]
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

local function append_text_token(tokens, value)
  if not value or value == '' then
    return
  end
  if #tokens > 0 and tokens[#tokens].kind == 'text' then
    tokens[#tokens].value = tokens[#tokens].value .. value
  else
    tokens[#tokens + 1] = { kind = 'text', value = value }
  end
end

local function parse_siunitx_unit(unit_spec)
  local numerator = {}
  local denominator = {}
  local target = numerator
  local pending_prefix = ''
  local pending_power = nil
  local i = 1
  local len = #unit_spec

  local function push_unit(list, symbol, exponent)
    if symbol == '' then
      return
    end
    list[#list + 1] = {
      symbol = symbol,
      exponent = exponent or '1',
    }
  end

  while i <= len do
    local ch = unit_spec:sub(i, i)

    if ch == '\\' then
      local j = i + 1
      while j <= len and unit_spec:sub(j, j):match('%a') do
        j = j + 1
      end
      if j == i + 1 then
        return nil
      end
      local cmd = unit_spec:sub(i + 1, j - 1)

      if cmd == 'per' then
        target = denominator
        pending_prefix = ''
        pending_power = nil
        i = j
      elseif cmd == 'cubic' then
        pending_power = '3'
        i = j
      elseif cmd == 'square' then
        pending_power = '2'
        i = j
      elseif SIUNITX_PREFIXES[cmd] then
        pending_prefix = pending_prefix .. SIUNITX_PREFIXES[cmd]
        i = j
      elseif SIUNITX_UNITS[cmd] then
        local symbol = pending_prefix .. SIUNITX_UNITS[cmd]
        pending_prefix = ''
        local exponent = pending_power or '1'
        pending_power = nil

        local next_char = unit_spec:sub(j, j)
        local next_index = j
        if next_char == '^' or next_char == '_' then
          local value, after = read_super_sub(unit_spec, j + 1)
          if not value then
            return nil
          end
          local sanitized = sanitize_plain_text(value)
          if not sanitized then
            return nil
          end
          if next_char == '^' then
            exponent = sanitized
          else
            symbol = symbol .. sanitized
          end
          next_index = after
        end

        if target == denominator then
          push_unit(denominator, symbol, exponent)
        else
          push_unit(numerator, symbol, exponent)
        end
        i = next_index
      else
        return nil
      end
    elseif ch:match('%s') then
      i = i + 1
    elseif ch == '^' or ch == '_' then
      local value, next_index = read_super_sub(unit_spec, i + 1)
      if not value then
        return nil
      end
      local sanitized = sanitize_plain_text(value)
      if not sanitized then
        return nil
      end
      local active = target == denominator and denominator or numerator
      local last_unit = active[#active]
      if not last_unit then
        return nil
      end
      if ch == '^' then
        last_unit.exponent = sanitized
      else
        last_unit.symbol = last_unit.symbol .. sanitized
      end
      i = next_index
    elseif ch == '{' then
      local content, next_index = read_group(unit_spec, i)
      if not content then
        return nil
      end
      local sanitized = sanitize_plain_text(content)
      if not sanitized or sanitized == '' then
        i = next_index
      else
        local active = target == denominator and denominator or numerator
        push_unit(active, sanitized, '1')
        i = next_index
      end
    else
      if ch == '/' then
        target = denominator
      else
        local active = target == denominator and denominator or numerator
        push_unit(active, ch, '1')
      end
      i = i + 1
    end
  end

  return numerator, denominator
end

local function build_unit_tokens(numerator, denominator)
  local tokens = {}

  for idx, unit in ipairs(numerator) do
    if idx > 1 then
      append_text_token(tokens, ' ')
    end
    append_text_token(tokens, unit.symbol)
    if unit.exponent and unit.exponent ~= '' and unit.exponent ~= '1' then
      tokens[#tokens + 1] = { kind = 'sup', value = unit.exponent }
    end
  end

  if #denominator > 0 then
    if #tokens > 0 then
      append_text_token(tokens, ' ')
    end
    append_text_token(tokens, '/')
    if #denominator > 1 then
      append_text_token(tokens, '(')
    end
    for idx, unit in ipairs(denominator) do
      if idx > 1 then
        append_text_token(tokens, ' ')
      end
      append_text_token(tokens, unit.symbol)
      local exponent = unit.exponent or '1'
      if exponent ~= '' and exponent ~= '1' then
        if exponent:sub(1, 1) ~= '-' then
          exponent = '-' .. exponent
        end
        tokens[#tokens + 1] = { kind = 'sup', value = exponent }
      end
    end
    if #denominator > 1 then
      append_text_token(tokens, ')')
    end
  end

  return tokens
end

local function parse_siunitx_command(cmd, math_text, index)
  if cmd == 'num' then
    local value, next_index = read_group(math_text, index)
    if not value then
      return nil, nil
    end
    local sanitized = sanitize_plain_text(value)
    if not sanitized then
      return nil, nil
    end
    local tokens = {}
    append_text_token(tokens, sanitized)
    return tokens, next_index
  elseif cmd == 'si' then
    local unit_spec, next_index = read_group(math_text, index)
    if not unit_spec then
      return nil, nil
    end
    local numerator, denominator = parse_siunitx_unit(unit_spec)
    if not numerator then
      return nil, nil
    end
    local unit_tokens = build_unit_tokens(numerator, denominator)
    return unit_tokens, next_index
  else
    local value, after_value = read_group(math_text, index)
    if not value then
      return nil, nil
    end
    local sanitized_value = sanitize_plain_text(value)
    if not sanitized_value then
      return nil, nil
    end
    local unit_spec, next_index = read_group(math_text, after_value)
    if not unit_spec then
      return nil, nil
    end
    local numerator, denominator = parse_siunitx_unit(unit_spec)
    if not numerator then
      return nil, nil
    end
    local unit_tokens = build_unit_tokens(numerator, denominator)
    local tokens = {}
    append_text_token(tokens, sanitized_value)
    if #unit_tokens > 0 then
      append_text_token(tokens, ' ')
      for _, token in ipairs(unit_tokens) do
        if token.kind == 'text' then
          append_text_token(tokens, token.value)
        else
          tokens[#tokens + 1] = token
        end
      end
    end
    return tokens, next_index
  end
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
    if SIUNITX_COMMANDS[cmd] then
      local tokens, next_index = parse_siunitx_command(cmd, math_text, j)
      if not tokens then
        return nil, nil
      end
      return {
        kind = 'tokens',
        tokens = tokens,
        force_plain = true,
      }, next_index
    elseif TEXT_COMMANDS[cmd] then
      local content, next_index = read_group(math_text, j)
      if not content then
        return nil, nil
      end
      local sanitized = sanitize_plain_text(content)
      if not sanitized then
        return nil, nil
      end
      if sanitized ~= '' then
        return {
          kind = 'text',
          value = sanitized,
          force_plain = true,
        }, next_index
      end
      return { kind = 'noop' }, next_index
  elseif WHITESPACE_COMMANDS[cmd] then
      return { kind = 'text', value = ' ' }, j
  elseif GREEK_COMMANDS[cmd] then
      return { kind = 'text', value = GREEK_COMMANDS[cmd] }, j
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
  elseif cmd == 'xrightarrow' or cmd == 'xleftarrow' then
      local label, next_index = read_group(math_text, j)
      local arrow_tokens = {}
      append_text_token(
        arrow_tokens,
        cmd == 'xrightarrow' and '→' or '←'
      )
      if label and label ~= '' then
        local sanitized = sanitize_plain_text(label)
        if sanitized and sanitized ~= '' then
          arrow_tokens[#arrow_tokens + 1] = {
            kind = 'sup',
            value = sanitized,
          }
        end
      end
      return {
        kind = 'tokens',
        tokens = arrow_tokens,
        force_plain = true,
      }, next_index or j
  elseif SYMBOL_COMMANDS[cmd] then
      return { kind = 'text', value = SYMBOL_COMMANDS[cmd] }, j
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
  local has_decorators = false
  local force_plain = false

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
        if result.force_plain then
          force_plain = true
        end
      elseif result.kind == 'tokens' then
        flush_buffer()
        for _, token in ipairs(result.tokens) do
          if token.kind == 'text' then
            tokens[#tokens + 1] = { kind = 'text', value = token.value }
          elseif token.kind == 'sup' or token.kind == 'sub' then
            tokens[#tokens + 1] = {
              kind = token.kind,
              value = token.value,
            }
            has_decorators = true
          end
        end
        if result.force_plain then
          force_plain = true
        end
      elseif result.kind == 'sup' or result.kind == 'sub' then
        flush_buffer()
        tokens[#tokens + 1] = result
        has_decorators = true
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
      has_decorators = true
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

  if not has_letter and not has_decorators and not force_plain then
    return nil
  end

  for _, token in ipairs(tokens) do
    if token.kind == 'text' then
      if token.value:find('=') then
        return nil
      end
      if token.value:find('[<>]') then
        return nil
      end
    end
  end

  tokens._force_plain = force_plain
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

local function tokens_have_digit(tokens)
  for _, token in ipairs(tokens) do
    local value = token.value or ''
    if value:find('%d') then
      return true
    end
  end
  return false
end

local function tokens_have_uppercase(tokens)
  for _, token in ipairs(tokens) do
    if token.kind == 'text' then
      local value = token.value or ''
      if value:find('%u') then
        return true
      end
    end
  end
  return false
end

local function tokens_have_digit_in_text(tokens)
  for _, token in ipairs(tokens) do
    if token.kind == 'text' then
      local value = token.value or ''
      if value:find('%d') then
        return true
      end
    end
  end
  return false
end

local function contains_decorators(tokens)
  for _, token in ipairs(tokens) do
    if token.kind == 'sup' or token.kind == 'sub' then
      return true
    end
  end
  return false
end

local function tokens_to_inlines(tokens)
  local inlines = {}

  for _, token in ipairs(tokens) do
    if token.kind == 'text' then
      local value = token.value or ''
      if value ~= '' then
        inlines[#inlines + 1] = pandoc.Str(value)
      end
    elseif token.kind == 'sup' then
      inlines[#inlines + 1] = pandoc.Superscript({pandoc.Str(token.value)})
    elseif token.kind == 'sub' then
      inlines[#inlines + 1] = pandoc.Subscript({pandoc.Str(token.value)})
    end
  end

  if #inlines == 0 then
    return nil
  end

  return inlines
end

local function tokens_form_charge(tokens)
  if #tokens ~= 1 then
    return nil
  end
  local token = tokens[1]
  if token.kind ~= 'sup' then
    return nil
  end
  local value = token.value or ''
  local trimmed = value:gsub('%s+', '')
  if trimmed == '' then
    return nil
  end
  if trimmed:match('^[%+%-]+$') or trimmed:match('^%d+[%+%-]+$') then
    return trimmed
  end
  if trimmed:match('^[%+%-]+%d+$') then
    return trimmed
  end
  return nil
end

local function tokens_form_sub_fragment(tokens)
  if #tokens ~= 1 then
    return nil
  end
  local token = tokens[1]
  if token.kind ~= 'sub' then
    return nil
  end
  local value = token.value or ''
  if value:match('^%d+$') then
    return { pandoc.Subscript({pandoc.Str(value)}) }
  end
  return nil
end

local function tokens_form_isotope(tokens)
  if #tokens ~= 3 then
    return nil
  end
  local first = tokens[1]
  local second = tokens[2]
  local third = tokens[3]
  if first.kind ~= 'sup' or second.kind ~= 'sub' or third.kind ~= 'text' then
    return nil
  end
  local mass = first.value or ''
  local atomic = second.value or ''
  if mass == '' then
    return nil
  end
  if not atomic:match('^%d+$') then
    return nil
  end
  local symbol = third.value or ''
  local inlines = {
    pandoc.Superscript({pandoc.Str(mass)}),
  }
  if symbol ~= '' then
    inlines[#inlines + 1] = pandoc.Str(symbol)
  end
  return inlines
end

local function expression_has_text_command(expr)
  if not expr then
    return false
  end
  if expr:find('\\mathrm') then
    return true
  end
  if expr:find('\\text') then
    return true
  end
  if expr:find('\\textrm') then
    return true
  end
  if expr:find('\\operatorname') then
    return true
  end
  if expr:find('\\mbox') then
    return true
  end
  return false
end

local function expression_has_siunitx(expr)
  if not expr then
    return false
  end
  if expr:find('\\SI') then
    return true
  end
  if expr:find('\\si') then
    return true
  end
  if expr:find('\\num') then
    return true
  end
  return false
end

local function convert_tokens_to_inlines(tokens, expr)
  local charge = tokens_form_charge(tokens)
  if charge then
    return { pandoc.Superscript({pandoc.Str(charge)}) }
  end

  local isotope = tokens_form_isotope(tokens)
  if isotope then
    return isotope
  end

  local sub_fragment = tokens_form_sub_fragment(tokens)
  if sub_fragment then
    return sub_fragment
  end

  local force_plain = tokens._force_plain or false
  local digits_in_text = tokens_have_digit_in_text(tokens)
  local has_uppercase = tokens_have_uppercase(tokens)
  local has_text_command = expression_has_text_command(expr)
  local has_decorators = contains_decorators(tokens)

  local has_siunitx_expr = expression_has_siunitx(expr)

  if has_text_command and not has_siunitx_expr and digits_in_text and not has_decorators then
    warn_nonstandard_unit(expr)
  end

  local should_plain = force_plain or digits_in_text or has_uppercase or has_text_command

  if not should_plain then
    return nil
  end

  local direct = tokens_to_inlines(tokens)
  if direct then
    return direct
  end

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
  local has_decorators = expr:find('[%_%^]') ~= nil
  local has_siunitx = expression_has_siunitx(expr)
  local has_text_command = expression_has_text_command(expr)
  if not (has_decorators or has_siunitx or has_text_command) then
    return nil
  end

  local tokens = parse_math_inline(expr)
  if not tokens then
    return nil
  end

  return convert_tokens_to_inlines(tokens, expr)
end

return {
  {
    Math = transform_math,
  },
}
