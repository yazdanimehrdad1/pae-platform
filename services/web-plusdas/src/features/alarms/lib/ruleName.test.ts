import { describe, expect, it } from 'vitest';
import { RULE_NAME_MAX_LENGTH, validateRuleName } from './ruleName';

describe('validateRuleName', () => {
  it.each(['a', '_x', 'p2_high', 'T1_Top_Oil', 'a'.repeat(RULE_NAME_MAX_LENGTH)])('accepts %s', name => {
    expect(validateRuleName(name, [])).toBeNull();
  });

  it.each([
    ['', 'Required'],
    ['a'.repeat(RULE_NAME_MAX_LENGTH + 1), 'At most 150 characters'],
    ['2p_high', 'Must not start with a digit'],
    ['p2 high', 'Only letters, digits and underscore (_); a space is not allowed'],
    ['p2-high', 'Only letters, digits and underscore (_); "-" is not allowed'],
    ['température', 'Only letters, digits and underscore (_); "é" is not allowed'],
  ])('rejects %j', (name, error) => {
    expect(validateRuleName(name, [])).toBe(error);
  });

  it('rejects a name that exists in any case', () => {
    expect(validateRuleName('P2_PHASE_B_OVERCURRENT', ['p2_phase_b_overcurrent']))
      .toBe('A rule named "p2_phase_b_overcurrent" already exists');
  });
});
