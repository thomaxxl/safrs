import { normalizeDocument } from '../../src/normalize/normalizeDocument';

describe('normalizeDocument relationship collision aliasing', () => {
  it('keeps attribute and aliases relationship as rel_<name>', () => {
    const warn = jest.fn();

    const result = normalizeDocument(
      {
        data: [
          {
            id: '1',
            type: 'Order',
            attributes: {
              Customer: 'attribute-value',
              ShipName: 'Alpha'
            },
            relationships: {
              Customer: {
                data: { id: 'VINET', type: 'Customer' }
              }
            }
          }
        ],
        included: [
          {
            id: 'VINET',
            type: 'Customer',
            attributes: {
              CompanyName: 'Vins et alcools Chevalier'
            }
          }
        ]
      },
      {
        logger: { warn }
      }
    );

    const record = result.records[0] as Record<string, unknown>;
    expect(record.Customer).toBe('attribute-value');
    expect(record.rel_Customer).toMatchObject({
      id: 'VINET',
      ja_type: 'Customer',
      CompanyName: 'Vins et alcools Chevalier'
    });
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it('uses deterministic numeric suffix when rel_<name> already exists', () => {
    const warn = jest.fn();

    const result = normalizeDocument(
      {
        data: [
          {
            id: '1',
            type: 'Order',
            attributes: {
              Customer: 'attribute-value',
              rel_Customer: 'already-used'
            },
            relationships: {
              Customer: {
                data: { id: 'VINET', type: 'Customer' }
              }
            }
          }
        ],
        included: [
          {
            id: 'VINET',
            type: 'Customer',
            attributes: {
              CompanyName: 'Vins et alcools Chevalier'
            }
          }
        ]
      },
      {
        logger: { warn }
      }
    );

    const record = result.records[0] as Record<string, unknown>;
    expect(record.Customer).toBe('attribute-value');
    expect(record.rel_Customer).toBe('already-used');
    expect(record.rel_Customer_1).toMatchObject({
      id: 'VINET',
      ja_type: 'Customer'
    });
    expect(warn).toHaveBeenCalledTimes(1);
  });
});
