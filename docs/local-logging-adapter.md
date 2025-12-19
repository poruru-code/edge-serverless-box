# ローカル環境用ログアダプター設計

## 概要

Lambda関数の`CloudWatchLogger`を、ローカル環境ではVictoriaLogsへ送信します。

**既存のLambdaコードの修正は不要です。**

## 構成

```
CloudWatchLogger
    └── log_client: LogClientAdapter
            ├── LocalLogClient → VictoriaLogs (HTTP)
            └── CloudWatchLogClient → AWS CloudWatch
```

## 環境変数

| 変数                    | 説明               |
| ----------------------- | ------------------ |
| `LOCAL_LAMBDA_ENV=true` | ローカル環境フラグ |

## VictoriaLogs UI

- URL: `http://localhost:9428/select/vmui`
- 検索例: `log_group:"/local/lambda/system"`

## ファイル

- `lambda_functions/LayerLib/.../cloudwatch_logger.py` - アダプター実装
- `compose-internal/docker-compose.internal.yml` - VictoriaLogsサービス
- `docker-compose.yml` - ポート9428公開
