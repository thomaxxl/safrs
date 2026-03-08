import { normalizeAdminYaml } from '../../src/schema/normalizeAdminYaml';
import { buildListQuery } from '../../src/query/buildQuery';

describe('buildListQuery include defaults', () => {
  it('excludes to-one relationships marked disable_autoload from defaults', () => {
    const schema = normalizeAdminYaml({
      resources: {
        Order: {
          attributes: [{ name: 'Id' }],
          tab_groups: [
            {
              name: 'Customer',
              direction: 'toone',
              resource: 'Customer',
              fks: ['CustomerId']
            },
            {
              name: 'Employee',
              direction: 'toone',
              resource: 'Employee',
              fks: ['EmployeeId'],
              disable_autoload: true
            },
            {
              name: 'OrderDetailList',
              direction: 'tomany',
              resource: 'OrderDetail',
              fks: ['OrderId']
            }
          ]
        }
      }
    });

    const query = buildListQuery('Order', {}, schema);
    const include = String(query.include ?? '');

    expect(include).toContain('Customer');
    expect(include).not.toContain('Employee');
    expect(include).not.toContain('OrderDetailList');
  });
});
