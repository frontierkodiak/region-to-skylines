// Remove only this producer's new array when checking older producers' byte scopes.
export function beforeGameplayWater(text) {
  const marker = text.indexOf('"id": "water_risk"');
  const key = text.indexOf('"game_agreement":', marker);
  const begin = text.indexOf('[', key);
  let depth = 0, quoted = false, escaped = false, end = -1;
  for (let i = begin; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (escaped) escaped = false;
      else if (c === '\\') escaped = true;
      else if (c === '"') quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === '[') depth++;
    else if (c === ']' && --depth === 0) { end = i + 1; break; }
  }
  if (marker < 0 || key < 0 || begin < 0 || end < 0) throw new Error('Missing water-results array');
  const rows = JSON.parse(text.slice(begin, end));
  if (!rows.length) return text;
  if (!rows.every(row => row.study === 'pl1191-playable-water')) throw new Error('Unowned water rows cannot be removed from historical checks');
  return text.slice(0, begin) + '[]' + text.slice(end);
}
