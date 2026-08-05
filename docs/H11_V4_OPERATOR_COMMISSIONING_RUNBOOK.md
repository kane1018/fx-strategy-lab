# H-11 v4 Operator Commissioning Runbook（2026-08-05・G076/G077/G078状態）

このrunbookは、無人の自動売買完成（UIのARM ON/OFFで起動状態を変更できる仕様）へ向けた
**現在のgate状態**と**operatorが実行できる操作**・**ブロックされているgateとその解除経路**を
記録する。エージェントは実Keychain read・実Private GET・実broker POST・実通知・
LaunchAgent install・ARM実変更・実runtime state root書込を行わない（すべてoperator境界）。

## 1. 現在のgeneration状態（HEAD fc2d552・working tree clean）

| generation | 役割 | status | commissioning |
|---|---|---|---|
| **G076**（canonical） | 最終完成candidate（fake-only runtime） | `UNATTENDED_RUNTIME_REVIEWED_AWAITING_COMMISSIONING` | **AWAITING_OPERATION_60**（未実行） |
| G077 | read-back解決candidate（v1.1） | `G077_FAKE_ONLY_REVIEWED_AWAITING_COMMISSIONING` | 未commissioning（G078に超越） |
| G078 | read-back解決corrective（C1-C4） | `G078_FAKE_ONLY_REVIEWED_AWAITING_COMMISSIONING` | 未commissioning（現行candidate） |

commissioning evidence（G076）: `status=G076_FAKE_ONLY_REVIEW_CLEAR_AWAITING_OPERATION_60`、
`operation_60_executed=false`、`initial_atomic_activation_started=false`、
`release_activation_executed=false`、全カウント0、全authorization false。

## 2. Gate状態サマリ

| gate | 状態 | 理由 |
|---|---|---|
| テスト基盤（full suite） | **CLEAR** | 9078 passed / 0 failed |
| Ruff / diff check | **CLEAR** | — |
| 独立A/S/Oレビュー | **CLEAR** | G077・G078ともVETOなし |
| digest整合（S/D/G077/G078） | **CLEAR** | verify_g076_review_artifacts PASS |
| UI契約ロード | **CLEAR** | `_load_current_contract`成功 |
| **G076 operation 60** | **BLOCKED** | scriptの`main()`が`G076_OPERATION_60_FAKE_ONLY_CANDIDATE`で拒否 |
| **G076 initial activation** | **BLOCKED** | scriptの`main()`が`G076_INITIAL_ACTIVATION_FAKE_ONLY_CANDIDATE`で拒否 |
| **UI ARM ON/OFF（G076）** | **BLOCKED** | `G076_FAKE_ONLY_ARM_MUTATION_DISABLED` |
| **release capability** | **LOCKED** | initial activation未実行のため |

**結論**: G076はfake-only最終完成candidateであり、設計上**実commissioning（op60/activation/ARM）は
G076では実行できない**。G075は実op60が実行可能だったが（LaunchAgent install付き・PASSED実績）、
G076のAGENTS.md例外は「実operationはcanonical昇格後の別明示承認を必須」かつ
「LaunchAgent操作・operation 60・initial activation実行を許可しない」としてfake-onlyに凍結している。

## 3. operatorが今すぐ実行できる操作（read-only / no-POST）

### 3.1 Monday offline self-check（安全・オフライン・read-only）

```bash
cd /Users/naoikansui/Desktop/トレード
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/h11_auto_v4_monday_self_check.py --repository .
```

- **前提**: working treeがcleanであること（untrackedファイルがあると
  `SELF_CHECK_WORKTREE_NOT_CLEAN`）。本runbook自体はcommit後に実行する。
- 期待出力: `status=MONDAY_OFFLINE_SELF_CHECK_CLEAR generation=H11_AUTO_30M_20260802_G076
  reviewed_files_digest=sha256:9b16bc4c... generation_digest=sha256:963ca2d1...`
- 停止条件: `status=...ERROR...` または dirty tree・HEAD不一致・digest不一致で return 2
- 実施内容: repo gate（clean main・HEAD==origin/main）・generation digest検証・
  local checks（focused/related tests・ruff・danger scan相当）

### 3.2 ローカルUIの起動（ARM ON/OFF画面の確認・G076ではmutation不可）

```bash
# docs/H11_MANUAL_SIGNAL_UI_NO_POST.md の起動手順に従う（local server・常駐なし）
```

- G076ではPOST /on・/offは`G076_FAKE_ONLY_ARM_MUTATION_DISABLED`（409）で拒否される。
  これは**設計どおり**（fake-only）。UIが契約をロードできること（500でないこと）自体は
  A-1修正により確認済み。

### 3.3 （任意）shadow commissioning artifactの生成

```bash
backend/.venv/bin/python backend/scripts/h11_auto_v4_current_generation_shadow_commission.py
```

- 実runtime state root配下へshadow-commissioning evidenceを書く（operator実行のみ）。
- 必須ではない（read-back解決の結線前）。

## 4. ブロック解除のための経路（推奨順）

### Step A（エージェント実施・設計＋fake-only実装・operator承認必要）
**read-back実解決のruntime結線**: G078の`run_g078_unknown_resolution_once`を実際の
runtime（coordinator/write outcome層）へ接続する設計とfake-only実装。必須契約:
- write action UNKNOWN直後（15秒以内）に解決stepを呼び出す
- 解決stepの**全pre-start拒否**は、UNKNOWN write outcomeが実在する場合はterminal扱い
  （engage halt）— G078 C1のwiring契約
- 解決結果からallow値・permit・hard-guard解除値を生成しない（不変）

### Step B（operator実施・必須）
**launcher placeholder区画の充填**: `h11_auto_v4_unattended_live_scheduled_launcher.py`等の
`credential_pair`（実Keychain）・`client`（実httpx）・notification transport（実Pushover/SMTP）の
3区画をoperator自身が実装（エージェントは対象外・AGENTS.md既定方針）。heartbeat-chain policy値は
確定済み（60/300秒）。

### Step C（エージェント実施・設計＋実装・別明示承認必要）
**実commissioning可能な次generation（G079候補）**: G076のfake-only制約（op60/activation/ARM）
を解除し、実op60（LaunchAgent install付き・G075パターン）・initial activation・
UI ARM ON/OFF（G078 labelをAPIが受理）を可能にするgeneration。
- このgenerationのAGENTS.md例外は「実operationは別明示承認」を維持した上で
  op60/activation/ARM mutationを明示的に許可する形で新設
- 実op60実行 → resident readiness確認 → initial activation → durable switch確認の順
- broker POSTはさらに別activation boundary承認まで禁止（hard guard default-deny不変）

## 5. 安全境界（全Step共通・不変）

- 実Keychain・実Private GET・実broker POST・実通知・LaunchAgent install・ARM実変更・
  実runtime state root書込はすべてoperator実行
- hard guard（`assert_real_broker_post_allowed`）default-deny不変・allow bridge禁止・
  env/`.env`解除禁止・retry/repost/second attempt禁止
- `actual_post_authorized=false` / `broker_post_authorized=false` / `live_ready=false` /
  `unattended_live_supported=false` は実commissioning完了まで維持
- G076/G077/G078のmarker・HALT・state root・evidence（存在する場合）の変更・reset禁止

## 6. 現時点の推奨

1. **Step A（runtime結線の設計）を次に進める**（エージェント実施・fake-only・digest影響なしの
   設計書＋テストから開始し、operatorがレビュー後に実装承認）
2. Step B（launcher充填）はoperatorが並行して進められる
3. Step C（G079実commissioning generation）はStep A完了後・別明示承認で
