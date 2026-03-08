import { readFileSync } from 'node:fs';
import { parse } from 'yaml';
import { normalizeAdminYaml } from '../../src/schema/normalizeAdminYaml';
import { buildListQuery } from '../../src/query/buildQuery';

describe('buildListQuery filtering behavior (base milestone)', () => {
  const schema = normalizeAdminYaml(
    parse(readFileSync('test/fixtures/admin.yaml', 'utf8'))
  );

  it('ignores filter.q and warns', () => {
    const warn = jest.fn();

    const query = buildListQuery(
      'Order',
      {
        filter: {
          q: 'ship',
          CustomerId: 'VINET'
        }
      },
      schema,
      {
        logger: { warn }
      }
    );

    expect(query.filter).toBeUndefined();
    expect(query['filter[CustomerId]']).toBe('VINET');
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining('filter.q is not implemented')
    );
  });

  it('warns on unknown filter keys but passes them through', () => {
    const warn = jest.fn();

    const query = buildListQuery(
      'Order',
      {
        filter: {
          UnknownField: 'abc'
        }
      },
      schema,
      {
        logger: { warn }
      }
    );

    expect(query['filter[UnknownField]']).toBe('abc');
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("unknown filter key 'UnknownField'")
    );
  });

  it('warns on unknown include names but passes them through', () => {
    const warn = jest.fn();

    const query = buildListQuery(
      'Order',
      {
        meta: {
          include: ['NotARelationship']
        }
      },
      schema,
      {
        logger: { warn }
      }
    );

    expect(query.include).toContain('NotARelationship');
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("unknown include 'NotARelationship'")
    );
  });
});
