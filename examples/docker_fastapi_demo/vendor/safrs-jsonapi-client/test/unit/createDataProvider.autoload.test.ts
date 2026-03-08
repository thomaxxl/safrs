import { readFileSync } from 'node:fs';
import { parse } from 'yaml';
import { normalizeAdminYaml } from '../../src/schema/normalizeAdminYaml';
import { createDataProviderSync } from '../../src/react-admin/createDataProvider';

function createJsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'content-type': 'application/vnd.api+json'
    }
  });
}

describe('createDataProvider to-one autoload', () => {
  const schema = normalizeAdminYaml(
    parse(readFileSync('test/fixtures/admin.yaml', 'utf8'))
  );

  it('autoloads to-one relationship from FK when list response lacks relationship linkage', async () => {
    const fetchMock = jest.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes('/Order')) {
        return createJsonResponse({
          data: [
            {
              id: '10248',
              type: 'Order',
              attributes: {
                Id: 10248,
                CustomerId: 'VINET',
                ShipName: 'Vins order'
              }
            }
          ],
          meta: { count: 1 }
        });
      }

      if (url.includes('/Customer')) {
        return createJsonResponse({
          data: [
            {
              id: 'VINET',
              type: 'Customer',
              attributes: {
                CompanyName: 'Vins et alcools Chevalier'
              }
            }
          ],
          meta: { count: 1 }
        });
      }

      throw new Error(`Unexpected URL: ${url}`);
    });

    const dp = createDataProviderSync({
      schema,
      apiRoot: 'http://api.example.test/api/',
      fetch: fetchMock,
      logger: { warn: jest.fn() }
    });

    const result = await dp.getList('Order', {
      pagination: { page: 1, perPage: 1 }
    });

    expect(result.data).toHaveLength(1);
    const first = result.data[0] as Record<string, unknown>;
    expect(first.Customer).toMatchObject({
      id: 'VINET',
      ja_type: 'Customer',
      CompanyName: 'Vins et alcools Chevalier'
    });

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls.some((url) => url.includes('/Order'))).toBe(true);
    expect(urls.some((url) => url.includes('/Customer'))).toBe(true);
  });
});
