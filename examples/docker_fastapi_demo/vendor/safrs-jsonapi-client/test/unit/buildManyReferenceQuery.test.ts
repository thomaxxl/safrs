import { readFileSync } from 'node:fs';
import { parse } from 'yaml';
import { normalizeAdminYaml } from '../../src/schema/normalizeAdminYaml';
import { buildManyReferenceQuery } from '../../src/query/buildQuery';

describe('buildManyReferenceQuery', () => {
  const schema = normalizeAdminYaml(
    parse(readFileSync('test/fixtures/admin.yaml', 'utf8'))
  );

  it('treats plain underscore attributes as single FK target', () => {
    const query = buildManyReferenceQuery(
      'Category',
      {
        target: 'CategoryName_ColumnName',
        id: 'Beverages',
        pagination: { page: 1, perPage: 10 }
      },
      schema
    );

    expect(query['filter[CategoryName_ColumnName]']).toBe('Beverages');
  });

  it('splits only known composite synthetic targets', () => {
    const query = buildManyReferenceQuery(
      'Order',
      {
        target: 'City_Country',
        id: 'Seattle_USA',
        pagination: { page: 1, perPage: 10 }
      },
      schema
    );

    expect(query['filter[City]']).toBe('Seattle');
    expect(query['filter[Country]']).toBe('USA');
  });
});
