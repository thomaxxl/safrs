import { getTotal } from '../../src/normalize/getTotal';

describe('getTotal', () => {
  it('prefers meta.count over meta.total', () => {
    const total = getTotal({
      data: [],
      meta: { count: 50, total: 10 }
    });

    expect(total).toBe(50);
  });

  it('falls back to meta.total then data length', () => {
    const fromTotal = getTotal({ data: [], meta: { total: 42 } });
    expect(fromTotal).toBe(42);

    const fromData = getTotal({
      data: [
        { id: '1', type: 'Order' },
        { id: '2', type: 'Order' }
      ]
    });
    expect(fromData).toBe(2);
  });
});
