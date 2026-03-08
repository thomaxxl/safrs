import { normalizeAdminYaml } from '../../src/schema/normalizeAdminYaml';

describe('normalizeAdminYaml flag normalization', () => {
  it('prefers snake_case flags over camelCase and builds readonly attributes', () => {
    const schema = normalizeAdminYaml({
      resources: {
        Order: {
          type: 'Order',
          attributes: [
            { name: 'Id' },
            { name: 'ShipName', hide_edit: true, hideEdit: false },
            { name: 'Notes', hideEdit: true }
          ],
          tab_groups: [
            {
              name: 'Customer',
              direction: 'toone',
              resource: 'Customer',
              fks: ['CustomerId'],
              disable_autoload: true,
              disableAutoload: false,
              hide_list: true,
              hideList: false
            }
          ]
        }
      }
    });

    expect(schema.resources.Order.relationships[0].disableAutoload).toBe(true);
    expect(schema.resources.Order.relationships[0].hideList).toBe(true);

    expect(schema.readonlyAttributeSet.Order.has('ShipName')).toBe(true);
    expect(schema.readonlyAttributeSet.Order.has('Notes')).toBe(true);
  });
});
