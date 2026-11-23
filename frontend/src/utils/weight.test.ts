import { describe, expect, it } from 'vitest'
import { fromGrams, netWeight, toGrams } from './weight'

describe('weight arithmetic', () => {
  it('converts decimal strings to grams exactly', () => {
    expect(toGrams('82.5')).toBe(82500)
    expect(toGrams('0.001')).toBe(1)
    expect(toGrams('100')).toBe(100000)
  })
  it('rejects invalid input', () => {
    expect(toGrams('abc')).toBeNull()
    expect(toGrams('1.2345')).toBeNull()   // more than gram precision
    expect(toGrams('-5')).toBeNull()
  })
  it('computes net weight without float errors', () => {
    expect(netWeight('0.3', '0.1')).toBe('0.200')   // floats would give 0.19999999999999998
    expect(netWeight('82.5', '0.5')).toBe('82.000')
    expect(netWeight('10', '')).toBe('10.000')
  })
  it('handles negative net (tare > gross) so the form can show an error', () => {
    expect(netWeight('1', '2')).toBe('-1.000')
    expect(fromGrams(-1000)).toBe('-1.000')
  })
})
