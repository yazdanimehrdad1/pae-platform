import { describe, expect, it } from 'vitest';
import {
  bitSelectionId, decodeBit, decodeEnum, functionSelectionId, isBitfieldPoint, isEnumPoint, parseFunctionSelectionId, parseSelectionId, sortedBits,
} from '@/shared/lib/discretePoints';

describe('discrete point detection', () => {
  it('needs both the type and labels', () => {
    expect(isEnumPoint({ data_type: 'enum16', enum_detail: { '1': 'off' } })).toBe(true);
    expect(isEnumPoint({ data_type: 'enum16', enum_detail: {} })).toBe(false);
    expect(isEnumPoint({ data_type: 'uint16', enum_detail: { '1': 'off' } })).toBe(false);
    expect(isBitfieldPoint({ data_type: 'bitfield32', bitfield_detail: { '0': 'trip' } })).toBe(true);
    expect(isBitfieldPoint({ data_type: 'status_word16', bitfield_detail: { '0': 'trip' } })).toBe(true);
    expect(isBitfieldPoint({ data_type: 'bitfield16', bitfield_detail: null })).toBe(false);
  });
});

describe('sortedBits', () => {
  it('orders bits numerically past bit 9 and accepts the bit- prefix', () => {
    const bits = sortedBits({ 'bit-10': 'ten', '2': 'two', 'bit-0': 'zero', junk: 'ignored' });
    expect(bits).toEqual([{ bit: 0, label: 'zero' }, { bit: 2, label: 'two' }, { bit: 10, label: 'ten' }]);
  });
});

describe('selection ids', () => {
  it('round-trips a bit selection and leaves plain point ids alone', () => {
    expect(bitSelectionId(12, 3)).toBe('12:bit3');
    expect(parseSelectionId('12:bit3')).toEqual({ pointId: '12', bit: 3 });
    expect(parseSelectionId('12')).toEqual({ pointId: '12' });
  });
});

describe('decoding', () => {
  it('reads one bit, including above bit 31', () => {
    expect(decodeBit(0b1010, 1)).toBe(1);
    expect(decodeBit(0b1010, 2)).toBe(0);
    expect(decodeBit(2 ** 33, 33)).toBe(1);
    expect(decodeBit(4.0000001, 2)).toBe(1);
  });

  it('labels an enum value, or marks it unknown', () => {
    expect(decodeEnum(2, { '2': 'running' })).toBe('running');
    expect(decodeEnum(7, { '2': 'running' })).toBe('Unknown (7)');
  });
});

describe('function selection ids', () => {
  it('round-trips site and device functions, with an optional series index', () => {
    expect(functionSelectionId('site-poi-power')).toBe('fn:site-poi-power');
    expect(functionSelectionId('device-trend', 7)).toBe('fn:7:device-trend');
    expect(functionSelectionId('site-poi-power', undefined, 2)).toBe('fn:site-poi-power#2');

    expect(parseFunctionSelectionId('fn:site-poi-power')).toEqual({ name: 'site-poi-power', deviceId: undefined, seriesIndex: 0 });
    expect(parseFunctionSelectionId('fn:7:device-trend#1')).toEqual({ name: 'device-trend', deviceId: '7', seriesIndex: 1 });
  });

  it('is never a point or bit selection, and point ids are not functions', () => {
    expect(parseFunctionSelectionId('12')).toBeNull();
    expect(parseFunctionSelectionId('12:bit3')).toBeNull();
    expect(parseFunctionSelectionId('fn:')).toBeNull();
    expect(parseSelectionId('12:bit3')).toEqual({ pointId: '12', bit: 3 });
    expect(parseSelectionId('fn:7:device-trend')).toEqual({ pointId: 'fn:7:device-trend' });
  });
});
