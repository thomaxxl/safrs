import { readFileSync } from 'node:fs';
import { parse } from 'yaml';
import { normalizeAdminYaml } from '../../src/schema/normalizeAdminYaml';

describe('normalizeAdminYaml', () => {
  it('normalizes resources and indexes', () => {
    const raw = parse(readFileSync('test/fixtures/admin.yaml', 'utf8'));
    const schema = normalizeAdminYaml(raw);

    expect(schema.resources.Order.endpoint).toBe('Order');
    expect(schema.resources.Order.type).toBe('Order');
    expect(schema.resourceByType.Order).toBe('Order');
    expect(schema.attributeNameSet.Order.has('CustomerId')).toBe(true);
    expect(schema.relationshipsByName.Order.Customer.direction).toBe('toone');
    expect(schema.relationshipsByName.Order.OrderDetailList.direction).toBe('tomany');
  });

  it('builds composite target indexes from relationship fks', () => {
    const raw = parse(readFileSync('test/fixtures/admin.yaml', 'utf8'));
    const schema = normalizeAdminYaml(raw);

    const orderComposites = schema.compositeTargets.Order;
    expect(orderComposites.has('City_Country')).toBe(true);
    expect(orderComposites.get('City_Country')).toEqual(['City', 'Country']);

    // Attribute names containing underscores must not be auto-split.
    expect(orderComposites.has('CategoryName_ColumnName')).toBe(false);
  });
});
