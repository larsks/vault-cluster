disable_mlock = true
ui = true
storage "raft" {
  path = "/vault/data"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_disable = true
}
