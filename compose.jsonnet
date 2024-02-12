local number_of_nodes = 3;

local vault(id, port_forward=false) = {
  image: 'docker.io/hashicorp/vault:1.15.5',
  cap_add: [
    'IPC_LOCK',
  ],
  volumes: [
    std.format('vault%d-data:/vault/data', id),
    './config:/vault/config:z',
  ],
  entrypoint: ['sh', '-c', |||
    chown -R vault /vault/data
    exec su-exec vault vault server --non-interactive --config=/vault/config
  |||],
  environment: {
    VAULT_ADDR: 'http://127.0.0.1:8200',
    VAULT_CLUSTER_ADDR: std.format('http://vault%d:8201', id),
    VAULT_API_ADDR: 'http://127.0.0.1:8200',
  },
  hostname: std.format('vault%d', id),
} + if port_forward then { ports: [std.format('%d:8200', 8200 + id)] } else {};

local vault_nodes = {
  [std.format('vault%d', id)]: vault(id)
  for id in std.range(0, number_of_nodes - 1)
};

local vault_volumes = {
  [std.format('%s-data', k)]: null
  for k in std.objectFields(vault_nodes)
};

local vault_addrs = [
  std.format('http://%s:8200', k)
  for k in std.objectFields(vault_nodes)
];

local vaultomatic = {
  vaultomatic: {
    build: {
      context: '.',
      dockerfile: 'Containerfile',
    },
    environment: {
      VAULT_ADDRS: std.join(' ', vault_addrs),
    },
  },
};

{
  volumes: vault_volumes,
  services: vault_nodes + vaultomatic,
}
