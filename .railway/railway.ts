import { defineRailway, image, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const mysqlVolume = volume("mysql-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "iad", sizeMB: 500 });
  const mnemosineVolume = volume("mnemosine-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "iad", sizeMB: 500 });
  const Mnemosine = service("Mnemosine", {
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    healthcheck: "/api/ready",
    healthcheckTimeout: 240,
    deploy: { restartPolicyType: "ON_FAILURE", restartPolicyMaxRetries: 3 },
    replicas: { "iad": 1 },
    networking: { privateNetworkEndpoint: "mnemosine" },
    volumeMounts: { "/data": mnemosineVolume },
  });
  const MySQL = service("MySQL", {
    source: image("mysql:8.4"),
    build: { buildEnvironment: "V3", builder: "RAILPACK" },
    replicas: { "iad": 1 },
    networking: { privateNetworkEndpoint: "mysql" },
    volumeMounts: { "/var/lib/mysql": mysqlVolume },
  });

  return project("Mnemosine", {
    variables: { managed: false },
    resources: [Mnemosine, MySQL, mysqlVolume, mnemosineVolume],
  });
});
