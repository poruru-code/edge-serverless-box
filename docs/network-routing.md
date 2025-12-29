# ネットワーク/ルーティング概要

このドキュメントは、Edge Serverless Box（Phase B）における「local-proxy + DNAT」
構成（P0）のネットワーク設計を説明します。パケットの流れ、iptables ルール、
およびトラブルシュート方法をまとめています。

## スコープと目的

- Lambda SDK/内部呼び出しのための `10.88.0.1` 互換を維持する
- 外部サービス（S3/DB/Logs）の固定 IP 依存を撤廃する
- DNAT を local L4 proxy（HAProxy）に集約し、Docker DNS でバックエンド解決する
- Phase C（Firecracker）への互換性を維持する

## コンポーネントと役割

- runtime-node:
  - containerd + CNI bridge（`10.88.0.0/16`）を実行
  - DNAT 用 iptables ルールを管理
  - gateway / agent / local-proxy と NetNS を共有
- local-proxy（HAProxy）:
  - runtime-node の NetNS 内で `127.0.0.1:9000/8001/9428` にバインド
  - Docker DNS で `s3-storage` / `database` / `victorialogs` を解決して TCP 転送
- gateway:
  - HTTPS エントリポイント（`:443`）
  - `worker.ip:8080` へ Invoke
  - `10.88.0.1:9428` へログ送信（DNAT -> local-proxy）
- agent:
  - containerd 経由で task を作成し CNI 接続
- worker（Lambda コンテナ）:
  - boto3 のエンドポイント:
    - S3: `http://10.88.0.1:9000`
    - DynamoDB: `http://10.88.0.1:8001`
    - Logs: `http://10.88.0.1:9428`

## Network Namespace

- runtime-node の NetNS を共有するもの:
  - gateway
  - agent
  - local-proxy
- Lambda worker は CNI bridge（`10.88.0.0/16`）へ接続

## トラフィックフロー

1) Client -> Gateway（HTTPS）
- 経路: Host `:443` -> runtime-node NetNS -> gateway

2) Gateway -> Worker（Invoke）
- 経路: gateway -> `worker.ip:8080`

3) Worker -> Gateway（Lambda chain invoke）
- 経路: worker -> `https://10.88.0.1:443`
- 443 は DNAT 不要（gateway は runtime-node NetNS 上に常駐）

4) Worker -> S3 / DynamoDB / VictoriaLogs
- 経路: worker -> `10.88.0.1:9000|8001|9428`
- iptables DNAT -> `127.0.0.1:9000|8001|9428`
- local-proxy -> DNS でバックエンド転送（`s3-storage`, `database`, `victorialogs`）

5) Gateway -> VictoriaLogs
- 経路: gateway -> `http://10.88.0.1:9428`
- (4) と同じ DNAT + local-proxy 経由

## DNAT ルール（runtime-node）

runtime-node の entrypoint が以下を設定します:

- `10.88.0.1:9000` -> `127.0.0.1:9000` -> local-proxy -> `s3-storage:9000`
- `10.88.0.1:8001` -> `127.0.0.1:8001` -> local-proxy -> `database:8000`
- `10.88.0.1:9428` -> `127.0.0.1:9428` -> local-proxy -> `victorialogs:9428`

適用範囲:
- PREROUTING（worker からの CNI トラフィック）
- OUTPUT（runtime-node NetNS 内のトラフィック）

注意: `127.0.0.1` への DNAT には `route_localnet=1` が必須です。  
`services/runtime-node/entrypoint.sh` で設定しています。

## 主要な環境変数

- `CNI_GW_IP`（既定: `10.88.0.1`）
- `DNAT_S3_IP`, `DNAT_DB_IP`, `DNAT_VL_IP`
  - local-proxy モード: `127.0.0.1`
  - 空文字の場合は DNAT ルールを作成しない
- `DNAT_DB_PORT`（既定: `8000`）
- `DNAT_DB_DPORT`（既定: `8001`）
- `DNAT_APPLY_OUTPUT`（既定: `1`）
- `GATEWAY_INTERNAL_URL`（既定: `https://10.88.0.1:443`）
- `VICTORIALOGS_URL`（既定: `http://10.88.0.1:9428`）

## local-proxy（HAProxy）設定

設定ファイル: `config/haproxy.cfg`

- バインド:
  - `127.0.0.1:9000` -> `s3-storage:9000`
  - `127.0.0.1:8001` -> `database:8000`
  - `127.0.0.1:9428` -> `victorialogs:9428`
- Docker DNS（`127.0.0.11`）を利用

## トラブルシュート

1) DNAT ルール確認
```
docker exec esb-runtime-node iptables -t nat -S
docker exec esb-runtime-node iptables -t nat -L PREROUTING -n -v
```

2) route_localnet（1であること）
```
docker exec esb-runtime-node cat /proc/sys/net/ipv4/conf/all/route_localnet
```

3) local-proxy の解決/疎通確認
```
docker logs --tail=200 esb-local-proxy
```

4) runtime-node NetNS から DNAT を確認
```
docker exec esb-runtime-node curl -f http://10.88.0.1:9000/health
```

5) worker から gateway 到達確認
```
docker exec esb-runtime-node curl -k https://10.88.0.1/health
```

## Phase C への影響

- DNAT + local-proxy モデルは Phase C でも維持する
- worker がコンテナから microVM に変わるだけ
- `10.88.0.1` 互換は必須条件のまま
