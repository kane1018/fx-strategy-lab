# 実装依頼: H-11 v4 実通知transport（Pushover / SMTP）

このドキュメントは、外部の開発者・AIアシスタントへ渡すための**実装依頼書**である。
リポジトリ: `fx-strategy-lab`（ローカル: `~/Desktop/トレード`）、ブランチ: `h11-v4-shadow-public-adapter`。

---

## 1. 依頼の要旨

無人自動売買スケジューラの最後の未実装部分である「**実際にPushover通知とメールを送信する
transportクラス2つ**」を実装してほしい。

既に決まっていること:

- 送信すべき内容・タイミング・失敗時の扱いは**すべて実装済み**。呼び出し側は完成している。
- 満たすべきインターフェース（Protocol）も**定義済み**。
- 実際にPushover APIを叩く／SMTPで送るコードも、**別用途（日次準備リハーサル）として既に存在する**。
- 使用するKeychainの項目も既に登録・運用されている。

つまり本依頼は「ゼロから設計する」仕事ではなく、**既存の実送信ロジックを、既存のProtocolに
適合する再利用可能なクラスとして組み直す**仕事である。

---

## 2. 成果物

新規ファイル1つ:

```
backend/app/services/h11_v4_notification_actual_transport.py
```

このファイルに、以下2クラスを実装する。

| クラス名（推奨） | 満たすProtocol | 役割 |
|---|---|---|
| `H11V4ActualPushoverTransport` | `H11V4PushoverTransport` | Pushover APIへ実HTTP POST |
| `H11V4ActualEmailTransport` | `H11V4EmailTransport` | SMTPで実メール送信 |

対応するテストファイル:

```
backend/app/tests/h11_auto/test_v4_notification_actual_transport_fake_only.py
```

---

## 3. 満たすべきインターフェース

定義元: `backend/app/services/h11_v4_notification_binding_no_post.py`（**このファイルは変更禁止**）

```python
@runtime_checkable
class H11V4PushoverTransport(Protocol):
    fake_only: bool
    def send_once(self, request: H11V4PushoverRequest) -> H11V4PushoverDelivery: ...

@runtime_checkable
class H11V4EmailTransport(Protocol):
    fake_only: bool
    def send_once(self, event: H11V4NotificationEvent) -> bool: ...
```

### 3.1 `fake_only` は必ず `False` にすること

呼び出し側は2箇所で厳密に検査する（`h11_v4_unattended_live_entry_notification.py`）:

```python
# unattended_live_notification_channel_ready(...)
return primary.fake_only is False and secondary.fake_only is False

# H11V4EnabledDualRouteNotifier.__post_init__
if self.primary.fake_only is not False or self.secondary.fake_only is not False:
    raise V4UnattendedLiveNotificationError("FAKE_NOTIFICATION_TRANSPORT_FORBIDDEN")
```

`is False` による同一性判定なので、`fake_only` は **bool型の `False` そのもの**である必要がある
（`0` や falsy な値では通らない）。インスタンス属性として存在させること（`isinstance()` による
runtime_checkable Protocol判定で属性の存在が確認される）。

### 3.2 入力: `H11V4PushoverRequest`

```python
@dataclass(frozen=True)
class H11V4PushoverRequest:
    event: H11V4NotificationEvent
    emergency_priority: bool
    receipt_required: bool
    retry_seconds: int | None      # critical時 60、それ以外 None
    expire_seconds: int | None     # critical時 3600、それ以外 None
```

`event` が `CRITICAL_EVENTS`（同ファイル内で定義）に含まれるかどうかで内容が決まる。

### 3.3 出力: `H11V4PushoverDelivery`

```python
@dataclass(frozen=True)
class H11V4PushoverDelivery:
    accepted: bool                      # Pushoverが送信を受理したか
    receipt_present: bool               # emergency送信のreceipt IDが得られたか
    acknowledged: bool                  # ユーザーがack（確認）したか
    external_send_performed: bool = False   # 実送信を行った場合 True を明示すること
```

email側は単に `bool`（送信成功なら `True`）を返す。

---

## 4. 呼び出し側の実際の挙動（重要）

`H11V4EnabledDualRouteNotifier.notify_once()` の判定ロジック:

```python
primary_ready = primary.accepted and (
    not request.receipt_required or (primary.receipt_present and primary.acknowledged)
)
secondary_ready = bool(secondary)
halt = not primary_ready or (event in CRITICAL_EVENTS and not secondary_ready)
```

`halt` が `True` になると、呼び出し元は
`UNATTENDED_ORCHESTRATION_NOTIFICATION_SEND_FAILED` を送出し、その実行を**中断する**
（リトライしない）。

### 4.1 現時点で実際に送られるイベントは1種類だけ

無人スケジューラ経路が送るのは `H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED` のみ
（`h11_v4_unattended_live_orchestration.py:160`）。

このイベントは **`CRITICAL_EVENTS` に含まれない**。したがって:

- `receipt_required=False`, `emergency_priority=False`, `retry_seconds=None`, `expire_seconds=None`
- `primary_ready` は `accepted` のみで決まる（**receiptのpolling・ack待ちは不要**）
- `secondary_ready`（メール）は halt 判定に影響しない

ただし **transportは汎用部品として、critical eventも正しく扱えるように実装すること**
（将来 `RESULT_UNKNOWN` や `KILL_ENGAGED` 等が同じtransportで送られる可能性がある）。
critical時は emergency priority=2 + retry/expire 付きで送信し、receipt IDを取得すること。

### 4.2 ack待ちのpollingについて

critical event の `acknowledged` をどう扱うかは実装判断が必要:

- 既存のリハーサル実装は最大15分間pollingしてackを待つ（`run_actual_pushover_rehearsal_once`）
- しかし**自動売買の実行パスで15分ブロックするのは不適切**（スケジューラのtickが詰まる）

**推奨**: transport自体は送信とreceipt取得までを行い、ack待ちは行わない。critical event では
`acknowledged` に「短時間（数秒〜十数秒）のpollingで確認できたか」を返すか、あるいは
ack待ちの有無を**コンストラクタ引数で選択可能**にする。いずれにせよ**上限秒数を必ず設け、
無制限にブロックしないこと**。この判断は実装者に委ねるが、選んだ方針をdocstringに明記すること。

---

## 5. 再利用すべき既存の実送信コード

`backend/app/services/h11_v4_notification_actual_preparation.py`（**変更禁止・参照のみ**）に、
実際に動作する送信ロジックが既にある。

### 5.1 Keychain読み出し（そのまま再利用可）

```python
from app.services.h11_v4_notification_actual_preparation import (
    H11V4NotificationCredentialBundle,   # .load_pushover_internal_only() / .load_smtp_internal_only()
)
```

- Keychain service: `fx-strategy-lab-h11-v4-notify`
- account: `pushover-api-token`, `pushover-user-key`, `smtp-username`, `smtp-app-password`
- 返り値は `_SealedNotificationSecret`。`.reveal_internal_only()` で値を取り出す。
  **取り出した値をログ・例外・repr・戻り値に含めてはならない。**

### 5.2 Pushover送信（ロジックを参考に再実装）

`run_actual_pushover_rehearsal_once` の内部処理を参照:

- POST先: `https://api.pushover.net/1/messages.json`
- form data: `token`, `user`, `title`, `message`, `priority`, `retry`, `expire`
- receipt確認: `https://api.pushover.net/1/receipts/{receipt}.json?token=...`
- 成功判定: HTTP 200 かつ レスポンスJSONの `status == 1`

### 5.3 SMTP送信（ロジックを参考に再実装）

`run_actual_smtp_rehearsal_once` の内部処理を参照:

- `smtp.gmail.com:587`、STARTTLS（`ssl.create_default_context(cafile=certifi.where())`）
- 送信先は自分自身（`smtp-username` の値をFrom/Toの両方に使う）

### 5.4 ただし「準備ゲート機構」は持ち込まないこと

既存の `run_actual_*_rehearsal_once` は、日次外部準備の1回限りの台帳
（`V4ExternalPreparationGate` / `V4PreparationOperationPermit` / `_attest_*_success_internal`）
に強く結合している。これは「1日1回の準備確認」用の仕組みであり、**毎エントリーサイクルで呼ぶ
transportがこれを使ってはならない**。

したがって **これらの関数を直接呼び出すのではなく、その内部の送信ロジック部分だけを新しい
クラスに再実装すること**。

---

## 6. このリポジトリの必須コーディング規約

安全性重視のプロジェクトのため、以下は必ず守ること。周辺のコードが良い手本になる。

1. **例外は固定の安全ラベルのみ**。専用の例外クラスを1つ定義し
   （例: `H11V4ActualNotificationTransportError`）、メッセージは
   `PUSHOVER_SEND_REJECTED_NO_RETRY` のような**固定文字列**にする。
   プロバイダのレスポンス本文・認証情報・アカウント名・受信者アドレスを**絶対に含めない**。
2. **リトライ禁止**。1回の呼び出しにつき1回の送信。失敗したら安全に失敗を返すか送出する。
3. **タイムアウト必須**。HTTP・SMTPとも明示的にタイムアウトを設定する（既存コードは10秒）。
4. **raw responseを保持しない**。必要な真偽値だけを取り出して捨てる。
5. **テスト可能な注入点を設ける**。既存コードと同様に、`httpx.Client` と SMTP factory を
   コンストラクタ引数（省略可・デフォルトは実物）として受け取れるようにする。
   これがないとテストが実ネットワークを叩いてしまう。
6. **`__bool__` は `False` を返す**（このプロジェクトの結果オブジェクトの慣習。
   「真偽値として誤用させない」ための意図的な設計）。
7. 型ヒントを付ける。`from __future__ import annotations` を先頭に置く。

---

## 7. テストの要件

`backend/app/tests/h11_auto/test_v4_notification_actual_transport_fake_only.py` に記述する。

**実ネットワーク・実Keychainへ絶対にアクセスしないこと。**

- `httpx.MockTransport` でPushover APIを模擬（既存テスト
  `test_v4_notification_binding_fake_only.py` や
  `test_v4_unattended_live_entry_gate_provider_no_post.py` が手本になる）
- SMTPは fake factory を注入
- Keychain読み出しは `H11V4NotificationCredentialBundle(reader=...)` に fake reader を渡す

最低限カバーすべきケース:

- [ ] 両クラスとも `fake_only is False` である
- [ ] `isinstance(instance, H11V4PushoverTransport)` / `isinstance(instance, H11V4EmailTransport)` が `True`
- [ ] `unattended_live_notification_channel_ready(primary=..., secondary=...)` が `True` を返す
- [ ] `H11V4EnabledDualRouteNotifier(primary=..., secondary=...)` が例外なく構築できる
- [ ] 非critical event（`UNATTENDED_LIVE_ENTRY_ATTEMPTED`）の送信が成功し、
      `notify_once(...).halt_required is False` になる
- [ ] Pushoverが `status != 1` を返したら安全ラベルで失敗する（リトライしない）
- [ ] HTTPエラー／ネットワークエラー時に安全ラベルで失敗する
- [ ] SMTP認証失敗・送信失敗時に安全ラベルで失敗する
- [ ] 例外メッセージ・repr に認証情報が一切現れない
- [ ] critical event で emergency priority / retry / expire が正しく設定される

---

## 8. 変更してはいけないファイル

以下は**参照のみ**。1行も変更しないこと。

- `backend/app/services/h11_v4_notification_binding_no_post.py`
- `backend/app/services/h11_v4_notification_actual_preparation.py`
- `backend/app/services/h11_v4_unattended_live_entry_notification.py`
- `backend/app/services/h11_v4_unattended_live_orchestration.py`
- `backend/app/services/h11_v4_gmo_g013_canary.py`
- `backend/app/h11_auto/` 配下のすべて
- `docs/templates/h11_v4_gmo_frozen_generation.json` の
  `implementation_digest` 以外のフィールド

またこの依頼の範囲外:

- ブローカー（GMOコイン）の認証情報・発注処理に関わる一切の変更
- スケジューラ・LaunchAgent・常駐プロセスの設定変更
- `broker_post_authorized` / `live_ready` / `unattended_live_supported` を `true` にすること

---

## 9. 完了後に必ず行う手順

### 9.1 新規モジュールを reviewed-files に登録

`backend/h11_v4_reviewed_digest.py` の `REVIEWED_FILES` タプルに、新規作成した
**2ファイル（実装・テスト）のパスを追加する**。

このプロジェクトは、レビュー済みソース全体のハッシュを世代契約に固定している。
通知系の既存モジュールもすべて登録済みなので、新規モジュールも登録しないと整合性検査の
対象外になってしまう。

### 9.2 テストとlint

```bash
cd backend
.venv/bin/python -m pytest app/tests/h11_auto -q     # 全件パスすること（現在 911 件）
ruff check <変更・追加したファイル>                      # クリーンであること
```

### 9.3 digest再計算とJSON更新

```bash
cd backend && .venv/bin/python -c "
from pathlib import Path
from h11_v4_reviewed_digest import compute_reviewed_files_digest
print(compute_reviewed_files_digest(repository=Path('..').resolve()))
"
```

出力された値を `docs/templates/h11_v4_gmo_frozen_generation.json` の
`implementation_digest` に反映する。

### 9.4 世代がロードできることを確認

```bash
cd backend && .venv/bin/python -c "
from pathlib import Path
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from h11_v4_reviewed_digest import compute_reviewed_files_digest
repo = Path('..').resolve()
d = compute_reviewed_files_digest(repository=repo)
g = load_v4_gmo_frozen_generation(repository=repo, implementation_digest=d)
print('OK', g.generation_label, g.digest)
"
```

`OK H11_AUTO_30M_20260725_G014 sha256:...` と出れば整合している。

---

## 10. 最終的な組み込み（依頼者本人が行う）

実装完了後、依頼者（リポジトリ所有者）が
`backend/scripts/h11_auto_v4_unattended_live_scheduled_launcher.py` の
`PLACEHOLDER 3 of 3` を、新クラスの構築に置き換える。

```python
notification_primary = _require_operator_configuration("PLACEHOLDER_3_NOTIFICATION_PRIMARY")
notification_secondary = _require_operator_configuration("PLACEHOLDER_3_NOTIFICATION_SECONDARY")
```
↓
```python
from app.services.h11_v4_notification_actual_preparation import (
    H11V4NotificationCredentialBundle,
)

notification_primary = H11V4ActualPushoverTransport(
    credentials=H11V4NotificationCredentialBundle(),
    client=httpx.Client(timeout=10.0),
)
notification_secondary = H11V4ActualEmailTransport(
    credentials=H11V4NotificationCredentialBundle(),
)
```

（独立レビュー2026-07-25の指摘により、`credentials`/`client`は必須引数へ変更された
— このtrack全体の「クレデンシャル関連は常にrequired・no-default」という規約に合わせるため。
`H11V4ActualPushoverTransport()`のような引数なし構築はできない。）

その後、9.3 の digest 再計算・JSON更新と、LaunchAgent の再インストールが再度必要になる。

**この最終組み込みステップは実装依頼の範囲に含めない。** 実際のブローカー口座に接続された
自動売買を有効化する操作であり、リポジトリ所有者本人が行う。

---

## 11. 補足: このスケジューラが今どういう状態か

- タイマー機構・digest検証・エントリーゲート判定・リスク管理は**すべて実装済み・レビュー済み**
- 実ブローカー認証情報とHTTPクライアントは**所有者本人が接続済み**
- **この通知transportだけが未実装**であり、そのためスケジューラは毎回ここで安全に停止している
- したがって本実装は「最後のピース」であり、完成すると**実際の自動発注が発生しうる状態になる**

この重みを理解した上で、上記の安全規約（固定安全ラベル・リトライ禁止・認証情報の非露出・
タイムアウト必須）を厳守すること。
