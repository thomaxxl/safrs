import { createDataProvider, loadAdminYamlFromUrl, normalizeAdminYaml } from '../../src';

const runIntegration = process.env.RUN_INTEGRATION === '1';
const describeIntegration = runIntegration ? describe : describe.skip;

describeIntegration('data provider integration (real API)', () => {
  jest.setTimeout(60000);

  const apiUrl = process.env.API_URL;
  const adminYamlUrl = process.env.ADMIN_YAML_URL;
  const resource = process.env.API_RESOURCE ?? 'Order';

  if (!apiUrl || !adminYamlUrl) {
    it('requires API_URL and ADMIN_YAML_URL', () => {
      throw new Error('Set RUN_INTEGRATION=1 with API_URL and ADMIN_YAML_URL');
    });
    return;
  }

  it('covers list/getOne/getMany/getManyReference basic contracts', async () => {
    const provider = await createDataProvider({
      apiRoot: apiUrl,
      adminYamlUrl,
      defaultPerPage: 3
    });

    const rawYaml = await loadAdminYamlFromUrl(adminYamlUrl, fetch);
    const schema = normalizeAdminYaml(rawYaml);

    const list = await provider.getList(resource, {
      pagination: { page: 1, perPage: 3 }
    });

    expect(list.data.length).toBeLessThanOrEqual(3);
    expect(typeof list.total).toBe('number');

    if (list.data.length === 0) {
      return;
    }

    const firstId = list.data[0].id as string | number;

    const one = await provider.getOne(resource, { id: firstId });
    expect(one.data.id).toBeDefined();

    const many = await provider.getMany(resource, { ids: [firstId] });
    expect(many.data.length).toBeGreaterThanOrEqual(1);

    const sourceSchema = schema.resources[resource];
    if (!sourceSchema) {
      return;
    }

    const rel = sourceSchema.relationships.find(
      (r) => r.direction === 'tomany' && r.fks.length === 1
    );

    if (!rel) {
      return;
    }

    const manyRef = await provider.getManyReference(rel.targetResource, {
      target: rel.fks[0],
      id: firstId,
      pagination: { page: 1, perPage: 3 }
    });

    expect(Array.isArray(manyRef.data)).toBe(true);
    expect(typeof manyRef.total).toBe('number');
  });
});
