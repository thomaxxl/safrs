import { normalizeAdminYaml } from '../../src/schema/normalizeAdminYaml';
import { sanitizeAttributes } from '../../src/write/sanitize';

describe('sanitizeAttributes readonly handling', () => {
  const schema = normalizeAdminYaml({
    resources: {
      Order: {
        type: 'Order',
        attributes: [
          { name: 'Id' },
          { name: 'ShipName', hide_edit: true },
          { name: 'Freight' }
        ]
      }
    }
  });

  it('drops readonly fields on update', () => {
    const warn = jest.fn();

    const result = sanitizeAttributes(
      'Order',
      {
        ShipName: 'Blocked',
        Freight: 12
      },
      schema,
      { warn },
      '1',
      'update'
    );

    expect(result.payload.data.attributes).toEqual({ Freight: 12 });
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining('readonly update attributes: ShipName')
    );
  });

  it('keeps readonly fields on create', () => {
    const result = sanitizeAttributes(
      'Order',
      {
        ShipName: 'AllowedOnCreate'
      },
      schema,
      undefined,
      undefined,
      'create'
    );

    expect(result.payload.data.attributes).toEqual({ ShipName: 'AllowedOnCreate' });
  });
});
