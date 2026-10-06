import { describe, expect, it } from 'vitest';
import { formatLabels, labelFields, labelKind, parseLabels } from '@/features/devices/lib/pointLabels';

describe('pointLabels', () => {
  it('knows which types take labels', () => {
    expect(['enum16', 'enum32', 'bitfield16', 'bitfield32', 'int16', 'status_word16'].map(labelKind)).toEqual([
      'enum', 'enum', 'bitfield', 'bitfield', null, null,
    ]);
  });

  it('formats in numeric order and parses back', () => {
    const text = formatLabels({ '10': 'TEN', '2': 'TWO' });
    expect(text).toBe('2=TWO; 10=TEN');
    expect(parseLabels(text, 'enum16')).toEqual({ labels: { '2': 'TWO', '10': 'TEN' }, error: null });
    expect(parseLabels('', 'int16')).toEqual({ labels: null, error: null });
    expect(parseLabels(' 03 = A = B \n4=C', 'enum16')).toEqual({ labels: { '3': 'A = B', '4': 'C' }, error: null });
  });

  it('rejects bad input', () => {
    expect(parseLabels('1=ON', 'int16').error).toMatch(/takes no labels/);
    expect(parseLabels('16=X', 'bitfield16').error).toMatch(/0–15/);
    expect(parseLabels('31=X', 'bitfield32').error).toBeNull();
    expect(parseLabels('x=Y', 'enum16').error).toMatch(/isn't a code/);
    expect(parseLabels('3=', 'enum16').error).toMatch(/has no label/);
    expect(parseLabels('ON', 'enum16').error).toMatch(/code=label/);
    expect(parseLabels('1=A; 01=B', 'enum16').error).toMatch(/twice/);
  });

  it('fills the detail that matches the type and clears the other', () => {
    expect(labelFields({ '1': 'A' }, 'enum16')).toEqual({ enum_detail: { '1': 'A' }, bitfield_detail: null });
    expect(labelFields({ '1': 'A' }, 'bitfield16')).toEqual({ enum_detail: null, bitfield_detail: { '1': 'A' } });
    expect(labelFields(null, 'int16')).toEqual({ enum_detail: null, bitfield_detail: null });
  });
});
