# H-11 v4 G078 Unknown-Resolution Runtime Wiring 設計書（Step A・fake-only・未結線）

- 日付: 2026-08-05
- 対象: G078のread-back解決step（`run_g078_unknown_resolution_once`）をruntimeの
  write outcome層へ接続する**wiring層**の設計とfake-only実装
- ステータス: **設計＋fake-only実装完了（runtime未結線・別StepでG079 generationに統合）**
- 前提: G077/G078はimmutable。本Stepの成果物（wiring module・test・設計書）は
  **全ファイル新規**であり、いずれのreviewed-files digestにも含めない（digest影響なし）。

## 1. 問題定義

- これまでの経緯: write actionのoutcomeがUNKNOWNになったとき、G076では即HALT
  （=generation terminal）だった。G077/G078はUNKNOWN直後のread-back解決で
  CONFIRMED_EXECUTED / CONFIRMED_NOT_EXECUTED / CONFIRMED_PARTIAL_FILL /
  UNRESOLVED に分類し、UNRESOLVED等のみterminalにする仕組み。
- **欠けている接続点**: 解決stepは存在するが、実際のruntime（write outcome層）から
  呼び出す**wiring層**がない。runtimeがUNKNOWNを観測した瞬間（15秒窓内）に解決stepを
  起動し、結果を解釈して次のアクション（OCO設定・次cycle・HALT）へ進める橋渡しが必要。
- G078 C1の契約: 「解決stepの全pre-start拒否は、UNKNOWN write outcomeが実在する場合
  terminal扱い（engage halt）」— この責務は解決step本体ではなく**呼び出し側（wiring層）**に
  割り当てられている（G078 runtime docstring）。本Stepはその呼び出し側を実装する。

## 2. 設計（wiring層）

### 2.1 モジュール

`backend/app/services/h11_v4_g078_unknown_resolution_wiring.py`

- 公開関数 `wire_unknown_write_outcome_resolution_once(...)` — 1 UNKNOWNに対して1回。
- 公開型 `G078WiringOutcome`（sanitized outcome・`__bool__`常にFalse）・`G078WiringError`。

### 2.2 呼び出し契約（runtime write path → wiring）

```
write action実行
  → outcome == UNKNOWN を観測（transport unknown_post_callback / coordinator outcome）
  → 直ちに（15秒窓内に）wire_unknown_write_outcome_resolution_once を1回呼ぶ
      state_root / generation_digest / reviewed_files_digest /
      action_scope_digest（そのwriteのopaque scope） / action_kind /
      read_back_client（G078FakeOnlyCallable・fake-only port） /
      unknown_observed_at_utc / now_utc / unknown_observed_monotonic（任意）
  → G078WiringOutcome を受け取り、action kind別に解釈
```

### 2.3 挙動（wiring層の責務）

1. 入力検証（digest形式・action kind・fake-only port・time tz）— 形式不正は
   `G078WiringError`（state不変）。
2. `run_g078_unknown_resolution_once` をそのまま呼ぶ（**分類ロジックを再実装しない**）。
3. 解決stepが**stateを返した**場合:
   - `CONFIRMED_EXECUTED` → policy `ACTION_CONFIRMED`（runtimeはaction kind別の後続
     actionへ: entry→OCO設定 / exit→flat確定）。
   - `CONFIRMED_NOT_EXECUTED` → policy `NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION`
     （同一M1 slot内の即時再入禁止・次scheduled cycleの新規観測のみ）。
   - `CONFIRMED_PARTIAL_FILL` / `UNRESOLVED` → 解決stepがHALTをlatch済み →
     outcomeの`halt_engaged=true`・`halt_reason`（module固有reasonを維持）。
4. 解決stepが**例外をraiseした**場合（C1 remainder）:
   - 当該scopeに**有効なevidence fileが存在** → 既に解決済み。recorded outcomeを返す
     （`G078_RESOLUTION_ALREADY_STARTED_NO_RETRY`の再呼び出し時）。
   - evidenceなし・HALTなし → `engage_g078_halt(reason=G078_WIRING_RESOLUTION_REFUSED_TERMINAL)`
     をlatchして `G078WiringError` をraise（未解決UNKNOWNを記録なしで残さない）。
   - HALT既存（解決stepがC1 reasonでlatch済み）→ **moduleの固有reasonを上書きしない**。
     そのまま `G078WiringError` をraise。
   - 非`G078Error`例外（read-back clientの想定外例外等）も同様にcatchして
     fail-closed（解決stepの`except G078Error`は通らないため、wiring層がterminal記録を保証）。
5. **許可値の非生成**: outcomeの`actual_post_authorized` / `broker_post_authorized` /
   `entry_authorized` は常にfalse。`__bool__`常にFalse。allow bridge・permit・
   hard-guard解除値なし。

### 2.4 解決stepとの責任分担

| 状況 | 誰がHALTをlatchするか | reason |
|---|---|---|
| 開始窓超過（wall/monotonic） | 解決step（C1） | `G078_RESOLUTION_START_WINDOW_EXCEEDED` |
| 予算枯渇 | 解決step（C1） | `G078_RESOLUTION_BUDGET_EXHAUSTED_TERMINAL` |
| UNRESOLVED / PARTIAL / TIMEOUT | 解決step | `G078_RESOLUTION_*` |
| post-start失敗 | 解決step（INTERNAL_FAILURE） | `G078_RESOLUTION_INTERNAL_FAILURE` |
| その他のpre-start拒否（digest/kind/port/time/lock/ALREADY_STARTED等） | **wiring層（C1 remainder）** | `G078_WIRING_RESOLUTION_REFUSED_TERMINAL` |
| 解決stepが非G078例外で異常終了 | **wiring層** | `G078_WIRING_RESOLUTION_REFUSED_TERMINAL` |

## 3. 不変境界（本Step）

- 実Keychain・実Private GET・実broker write・実通知・ARM変更・LaunchAgent操作なし。
- read-back clientは`G078FakeOnlyCallable`以外を拒否（解決stepも二重に拒否）。
- retry・repost・second attempt禁止（1 UNKNOWNにつきwiring呼び出し1回・解決1回）。
- 解決結果からallow値・permit・hard-guard解除値を生成しない。
- G077/G078 runtime・test・digest module・templateは一切変更しない。
- 本Stepの完了はruntime結線・live-ready・activation承認を意味しない。

## 4. fake-only acceptance matrix（実装済みテスト13件）

1. CONFIRMED_EXECUTED → outcome state/policy `ACTION_CONFIRMED`・haltなし
2. CONFIRMED_NOT_EXECUTED（exitの建玉所有）→ `NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION`
3. UNRESOLVED（曖昧）→ 解決stepがHALT latch → `halt_engaged=true`・module reason維持
4. 開始窓超過 → wiringはmoduleの固有reasonを上書きしない
5. ALREADY_STARTED（evidenceなし）→ wiringがHALT latch + raise（C1 remainder）
6. ALREADY_STARTED（evidenceあり）→ recorded outcomeを返す（再解決しない）
7. read-back clientの非G078例外 → wiringがHALT latch + raise（fail-closed）
8. 非fake client拒否（`G078_WIRING_FAKE_ONLY_READ_BACK_REQUIRED`）・state不変
9. digest形式不正拒否（`G078_WIRING_GENERATION_DIGEST_INVALID`）・state不変
10. outcomeは常にFalse・authorization false
11. 既存HALTをwiringが上書きしない
12. module source scan: httpx/Keychain/smtplib/subprocess/requests/Pushover/environ/
    launchd/private・public v1 token不在
13. wiringは解決stepへ直接delegate（`run_g078_unknown_resolution_once`呼び出し・
    allow値の構築なし）

## 5. 実装ファイル（全新規・digest影響なし）

| ファイル | 種別 |
|---|---|
| `docs/H11_V4_G078_UNKNOWN_RESOLUTION_WIRING_DESIGN.md` | 本設計書 |
| `backend/app/services/h11_v4_g078_unknown_resolution_wiring.py` | wiring層（fake-only） |
| `backend/app/tests/h11_auto/test_v4_g078_unknown_resolution_wiring_fake_only.py` | fake-onlyテスト13件 |

## 6. 次のStep（runtime結線・G079候補）

- G079 generationで: 実runtime write path（coordinator/transport）から本wiringを呼び出す
  結線・実read-back producer（G026 one-use Private GET方式・generation-bound）・
  op60/initial activation/ARM mutationを実許可するAGENTS.md例外・UI projection
  （`resolution_state`をarm/release/effective/entryと独立投影）。
- 実read-back producerとwiringはG079 reviewed digestへbindする（本Stepのファイル群を
  G079 reviewed filesに含めるかはG079設計時に確定）。

## 7. Definition of done（本Step）

- acceptance matrix 13件全PASS・focused/related tests・Ruff・diff check CLEAR
- フルスイート（backend/ CI構成）全緑（新規ファイルのみ・digest影響なし）
- 既存G076/G077/G078のbinding不変（`compute_*_reviewed_files_digest`値不変）
- 実Keychain・Private API・broker・通知・ARM・LaunchAgentへ未接続
- `actual_post_authorized=false` / `broker_post_authorized=false` / `live_ready=false` /
  `unattended_live_supported=false` を維持
