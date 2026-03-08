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

describe('createDataProvider bulk methods and update id conflict', () => {
  const schema = normalizeAdminYaml(
    parse(readFileSync('test/fixtures/admin.yaml', 'utf8'))
  );

  it('throws on update id conflict before issuing a request', async () => {
    const fetchMock = jest.fn(async () =>
      createJsonResponse({
        data: {
          id: '1',
          type: 'Order',
          attributes: {}
        }
      })
    );

    const dp = createDataProviderSync({
      schema,
      apiRoot: 'http://api.example.test/api/',
      fetch: fetchMock,
      logger: { warn: jest.fn() }
    });

    await expect(
      dp.update('Order', {
        id: '1',
        data: {
          id: '2',
          ShipName: 'X'
        }
      })
    ).rejects.toThrow('id conflict');

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('supports updateMany via per-id PATCH requests', async () => {
    const fetchMock = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const id = url.split('/').pop() ?? 'unknown';

      expect(init?.method).toBe('PATCH');
      return createJsonResponse({
        data: {
          id,
          type: 'Order',
          attributes: {
            ShipName: 'Bulk'
          }
        }
      });
    });

    const dp = createDataProviderSync({
      schema,
      apiRoot: 'http://api.example.test/api/',
      fetch: fetchMock,
      logger: { warn: jest.fn() }
    });

    const result = await dp.updateMany('Order', {
      ids: ['1', '2'],
      data: {
        ShipName: 'Bulk'
      }
    });

    expect(result.data).toEqual(['1', '2']);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('supports deleteMany via per-id DELETE requests', async () => {
    const fetchMock = jest.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('DELETE');
      return createJsonResponse({});
    });

    const dp = createDataProviderSync({
      schema,
      apiRoot: 'http://api.example.test/api/',
      fetch: fetchMock,
      logger: { warn: jest.fn() }
    });

    const result = await dp.deleteMany('Order', {
      ids: ['1', '2', '3']
    });

    expect(result.data).toEqual(['1', '2', '3']);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
