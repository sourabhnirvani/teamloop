// A phone showing the "desktop site" (Chrome's ⋮ → Desktop site, or a desktop-mode install) lays the page out
// ~980px wide and ignores the viewport tag, so the app would show its laptop layout in tiny type. When the
// screen itself is a phone's, use the phone layout anyway: the phone styles apply whatever the width, and the
// app is scaled up so it fills the screen at its normal size.

const PHONE = 760;
const screenWidth = typeof screen !== "undefined" ? Math.min(screen.width, screen.height) : 9999;
const touch = typeof matchMedia !== "undefined" && matchMedia("(pointer: coarse)").matches;

export const forcedPhone = touch && screenWidth <= PHONE && window.innerWidth > screenWidth + 40;

export function applyPhoneMode(): void {
  if (!forcedPhone) return;
  const root = document.documentElement;
  root.classList.add("phone-forced");
  root.style.setProperty("--fz", String(window.innerWidth / screenWidth));
  // copy the stylesheet's phone rules (@media max-width: 760px) so they apply at this width too
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      continue; // a stylesheet from another site (fonts): not ours
    }
    for (const rule of Array.from(rules)) {
      if (rule instanceof CSSMediaRule && /max-width:\s*760px/.test(rule.conditionText) && !/min-width/.test(rule.conditionText)) {
        const inner = Array.from(rule.cssRules).map((r) => r.cssText).join("\n");
        sheet.insertRule(`@media all { ${inner} }`, sheet.cssRules.length);
      }
    }
  }
}

export function isPhone(): boolean {
  return forcedPhone || window.innerWidth <= PHONE;
}
