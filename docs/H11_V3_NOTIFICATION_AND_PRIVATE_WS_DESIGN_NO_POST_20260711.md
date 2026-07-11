# H-11 v3 Notification / Private WebSocket Design（fake-only・no-POST）

Date: 2026-07-11

Status: **IMPLEMENTED_FAKE_ONLY_NOT_ACTIVATED**

## 目的

H-11 v3の監視経路を、Private WebSocket token provider、再接続client、外部notifierの3境界へ
分離する。今回実装するのは型、fail-closed状態遷移、fake binding、テストだけである。

## 境界

```text
fake token status provider
  -> bounded reconnect policy
  -> fake Private WS safe event categories
  -> fake external notifier
  -> heartbeat / dead-man / entry / settlement safe categories
```

- token値、credential値、event payload、ID、価格、口座情報を型へ渡さない。
- tokenがunavailable/expired/unknownなら接続せずdead-man haltを通知する。
- 接続試行上限へ到達したらdead-man haltとし、自動entryを許可しない。
- unknown eventまたはnotification failureはHALTとする。
- entry/settlementはsafe categoryだけを外部通知境界へ渡す。
- 再接続回数・backoff・外部通知先はactual activation前にoperatorが固定する。

## 今回の実装

- `H11V3PrivateWsTokenProvider` protocol
- `H11V3PrivateWsClient` protocol
- `H11V3ExternalNotifier` protocol
- fake token provider / fake reconnect client / fake external notifier
- heartbeat、dead-man、entry、settlement、unknownの発火テスト
- actual Private API call、actual WebSocket、メール/Webhook送信は0件

## activation時に残るoperator判断

- actual notification destinationと所有者
- actual accountでのPrivate WS token/API permission
- reconnect上限、backoff、heartbeat期限
- notification outage時の停止・手動復旧手順
- credentialのsealed provision方法

```text
actual_private_api_call_count=0
actual_ws_connection_count=0
external_send=false
credential_read=false
actual_post=false
```
