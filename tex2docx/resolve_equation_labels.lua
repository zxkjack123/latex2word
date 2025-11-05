if FORMAT:match('latex') then
  return {}
end

local nequations = 0
local equation_labels = {}

local function cite_for_reference(reference)
  local doc = pandoc.read("[-@" .. reference .. "]", "markdown")
  if doc.blocks and #doc.blocks == 1 then
    local block = doc.blocks[1]
    if block.t == "Para" then
      for _, inline in ipairs(block.c) do
        if inline.t == "Cite" then
          return inline
        end
      end
    end
  end

  return nil
end

local function find_label(txt)
  local before, label, after = txt:match('(.*)\\label%{(.-)%}(.*)')
  return label, label and (before .. after) or txt
end

return {
  {
    Math = function(m)
      if m.mathtype == pandoc.DisplayMath then
        local label, stripped = find_label(m.text)
        if label then
          nequations = nequations + 1
          equation_labels[label] = "(" .. tostring(nequations) .. ")"
          m.text = stripped
        end
      end
      return m
    end
  },
  {
    Link = function(link)
      local ref_type = link.attributes["reference-type"]
      local target = link.attributes["reference"]

      if target and target:match("^eq:") and equation_labels[target] then
        return pandoc.Str(equation_labels[target])
      end

      if ref_type and target then
        local cite = cite_for_reference(target)
        if cite then
          return cite
        end
      end

      return nil
    end
  }
}
