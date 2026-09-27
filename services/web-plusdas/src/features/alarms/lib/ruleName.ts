// Rule names become identifiers in backend-ot (a rule's variable name), so they follow the
// usual identifier rules and are unique regardless of case.

export const RULE_NAME_MAX_LENGTH = 150;
export const RULE_NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
export const RULE_NAME_HINT =
  `Used as an identifier in backend-ot: up to ${RULE_NAME_MAX_LENGTH} characters, only letters, digits and ` +
  "underscore (_), not starting with a digit, no spaces, unique (ignoring case).";

/** The first problem with a rule name as user-facing text, or null when it is valid. */
export function validateRuleName(name: string, existingNames: Iterable<string>): string | null {
  if (name === "") return "Required";
  if (name.length > RULE_NAME_MAX_LENGTH) return `At most ${RULE_NAME_MAX_LENGTH} characters`;
  if (/^[0-9]/.test(name)) return "Must not start with a digit";
  if (!RULE_NAME_PATTERN.test(name)) {
    const invalid = [...name].find(character => !/[A-Za-z0-9_]/.test(character))!;
    const shown = invalid === " " ? "a space" : `"${invalid}"`;
    return `Only letters, digits and underscore (_); ${shown} is not allowed`;
  }
  const lower = name.toLowerCase();
  for (const existing of existingNames) {
    if (existing.toLowerCase() === lower) return `A rule named "${existing}" already exists`;
  }
  return null;
}
