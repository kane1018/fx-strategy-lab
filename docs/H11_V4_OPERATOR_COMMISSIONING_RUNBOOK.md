# H-11 v4 Operator Commissioning Runbook（2026-08-06・G075状態）

このrunbookは、無人の自動売買完成（UIのARM ON/OFFで起動状態を変更できる仕様）へ向けた
**現在のgate状態**と**operatorが実行できる操作**・**ブロックされているgateとその解除経路**を
記録する。エージェントは実Keychain read・実Private GET・実broker POST・実通知・
LaunchAgent install・ARM実変更・実runtime state root書込を行わない（すべてoperator境界）。

canonical世代は **G075**（`H11_AUTO_30M_20260802_G075`・runtime-only corrective）である。
削除済み世代（G066〜G079のうちG075以外）を手順の前提にしないこと。

## 1. 現在のgeneration状態（HEAD fe0b7cb）

| generation | 役割 | status | commissioning |
|---|---|---|---|
| **G075**（canonical） | runtime-only corrective（no-POST） | `G075_RUNTIME_REVIEWED`（未レビュー） | **未commissioning**（op60未実行） |

G075のruntime state root（`backend/market_data/h11_v4_gmo_actual_runtime/generation-<code変更後のdigest>/`）は
**未作成**である。ディスク上には**未解決の永久HALTが2件** latchされている（削除・改変禁止）:

```
generation-ce098ee8…/g074-persistent-halt.json   G074_INITIAL_TRANSACTION_UNKNOWN
generation-f0e74bf0…/g075-persistent-halt.json   G075_INITIAL_TRANSACTION_UNKNOWN
```

いずれも `broker_post_count: 0` / `actual_post_count: 0` であり、実発注は発生していない。

## 2. Gate状態サマリ

| gate | 状態 | 理由 |
|---|---|---|
| テスト基盤（full suite） | **CLEAR** | 8941 passed / 0 failed（2026-08-06 Phase D hotfix 時点。増加は正常） |
| Ruff / diff check | **CLEAR** | — |
| 独立A/S/Oレビュー | **未CLEAR** | P0/Phase Aの変更は独立3レーンレビュー待ち |
| レビュー合格証ゲート `verify_g075_review_artifacts` | **拒否（正しい状態）** | 未レビューコードへのCLEAR移植を防ぐため。**通過させないこと** |
| digest整合（固定点） | **CLEAR** | §0 のコマンドで現在値を得ること（コード変更で動く） |
| UI契約ロード | **CLEAR** | `_load_current_contract`成功 |
| 未解決HALTスキャン `require_g075_no_unresolved_halt` | **拒否（正しい状態）** | ディスク上の未解決HALT2件を検出（`G075_UNRESOLVED_HALT_PRESENT`） |
| **G075 operation 60** | **BLOCKED** | レビュー合格証ゲートが拒否するため |
| **G075 initial activation** | **BLOCKED** | 同上 |
| **UI ARM ON（G075）** | **BLOCKED** | 未解決HALTスキャンが拒否（`G075_UNRESOLVED_HALT_PRESENT`） |
| **release capability** | **LOCKED** | initial activation未実行のため |

**結論**: G075は未レビュー・未commissioningであり、実op60/activation/ARMはすべて
ブロックされたままが正しい。HALTファイルの削除や digest 再ベイクで gate を「通す」ことは
**禁止**（過去2回のHALT脱出手段そのもの）。解除は operator の明示操作を要する別設計であり、
Phase A の対象外。

## 3. operatorが今すぐ実行できる操作（read-only / no-POST）

### 3.1 Monday offline self-check（安全・オフライン・read-only）

```bash
cd /Users/naoikansui/Desktop/トレード
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/h11_auto_v4_monday_self_check.py --repository .
```

- **前提**: working treeがcleanであること（untrackedファイルがあると
  `SELF_CHECK_WORKTREE_NOT_CLEAN`）。本runbook自体はcommit後に実行する。
- **G075 では `status=SELF_CHECK_G075_REVIEW_PENDING` で恒久的に失敗（return 2）するのが正常である。**
  これはレビュー未了を正直に表明する設計であり、**修理対象ではない**。G075 のレビュー合格証
  ゲートが拒否したままである限り、Monday self-check はこの結果を返し続ける。
- 期待出力（参考・クリア時）: `status=MONDAY_OFFLINE_SELF_CHECK_CLEAR
  generation=H11_AUTO_30M_20260802_G075 reviewed_files_digest=<現在値>
  generation_digest=<現在値>`（digest はコード変更で動く。§0 コマンドで得ること）
- 停止条件: `status=...ERROR...` または dirty tree・HEAD不一致・digest不一致で return 2

### 3.2 ローカルUIの起動（ARM ON/OFF画面の確認）

```bash
# docs/H11_MANUAL_SIGNAL_UI_NO_POST.md の起動手順に従う（local server・常駐なし）
```

- G075ではPOST /onは未解決HALTスキャンが拒否（`G075_UNRESOLVED_HALT_PRESENT`、409）。
  POST /off は常に通る（停止操作は阻害しない）。これは**設計どおり**。
  UIが契約をロードできること（500でないこと）自体は確認済み。

### 3.3 （任意）shadow commissioning artifactの生成

```bash
backend/.venv/bin/python backend/scripts/h11_auto_v4_current_generation_shadow_commission.py
```

- 実runtime state root配下へshadow-commissioning evidenceを書く（operator実行のみ）。
- 必須ではない。

### 3.4 HALT discharge（操作者専用・renameアーカイブのみ・Phase C）

ディスク上の未解決HALT2件（G074/G075）は実害なしと operator が判断した場合も、
**解除は必ずこの手続きで記録を残して行う**。削除は禁止、rename アーカイブのみ。

```bash
# 0) 対象halt(generation digestとファイル名)を事前に列挙する
find backend/market_data/h11_v4_gmo_actual_runtime -name "g0*-persistent-halt.json"
# パスは .../generation-<64桁hex>/gNNN-persistent-halt.json の形。
# --generation-digest には "sha256:" + <64桁hex> を、--halt-file-name には
# ファイル名をそのまま渡す。

# 1) 対象haltの内容とsha256を表示（スクリプトが表示する）
PYTHONPATH=backend backend/.venv/bin/python \
  backend/scripts/h11_auto_v4_halt_discharge.py \
  --repository . \
  --generation-digest sha256:f0e74bf0f3ef114db3474df4aa7348edf112a5c8534d55121f730173ea868c0d \
  --halt-file-name g075-persistent-halt.json \
  --operator "<operator名>" \
  --reason "<解除理由>" \
  --broker-state-confirmation "<建玉ゼロ・注文ゼロをいつどう確認したか>" \
  --confirm-sha256 sha256:<表示された値>
```

- 対象は明示した1ファイルのみ（glob一括解除なし）。`--confirm-sha256` が
  実ファイル内容の sha256 と一致しない限り実行されない。
- アーカイブは `g075-halt-discharged.<UTC日時>.json` として元内容を
  `original` に保持し、runtime の未解決HALTスキャン
  （`g0*-persistent-halt.json`）から外れる。
- **この手続きの実行は operator の判断に属する**。エージェントは実行しない。
  discharge は `actual_post_authorized` 等の能力フラグを一切変えない。

## 4. ブロック解除のための経路（推奨順）

### Step A（独立3レーンレビュー・必須）
P0（VETO解消）とPhase A（安全欠陥4件の修正）の変更全体を対象に、Architecture / Safety /
Operations の独立3レーンレビューを実施し、VETOなしとする。レビュー合格証
（`h11_v4_g075_runtime_commissioning_evidence.json` /
`h11_v4_g075_independent_review_attestation.json`）の digest 更新は、
**本物のレビューを実施しその結果を記録した副産物**としてのみ発生してよい。
ゲートを通すために書き換えることは禁止（自己署名パターン）。

### Step B（operator実施・必須）
**launcher placeholder区画の充填**: `h11_auto_v4_unattended_live_scheduled_launcher.py`等の
`credential_pair`（実Keychain）・`client`（実httpx）・notification transport（実Pushover/SMTP）の
3区画をoperator自身が実装（エージェントは対象外・AGENTS.md既定方針）。heartbeat-chain policy値は
確定済み（60/300秒）。

### Step C（G075 commissioning・それぞれ別明示承認必須）
G075の実op60（LaunchAgent install付き・G075パターン）→ initial activation →
UI ARM ON/OFF の順。各操作はoperatorの明示承認範囲でのみ行う。broker POSTはさらに
別activation boundary承認まで禁止（hard guard default-deny不変）。実op60実行前に、
ディスク上の未解決HALT2件の扱いをoperatorが明示決定する必要がある
（解除機構は未設計であり、Phase Aの対象外）。

## 5. 安全境界（全Step共通・不変）

- 実Keychain・実Private GET・実broker POST・実通知・LaunchAgent install・ARM実変更・
  実runtime state root書込はすべてoperator実行
- hard guard（`assert_real_broker_post_allowed`）default-deny不変・allow bridge禁止・
  env/`.env`解除禁止・retry/repost/second attempt禁止
- `actual_post_authorized=false` / `broker_post_authorized=false` / `live_ready=false` /
  `unattended_live_supported=false` は実commissioning完了まで維持
- `market_data/**/g0*-persistent-halt.json` の削除・改変禁止（未解決事象の証跡）

## 6. 現時点の推奨

1. **Step A（独立3レーンレビュー）を次に進める**（P0 + Phase A の差分をレビュー）
2. Step B（launcher充填）はoperatorが並行して進められる
3. Step C（G075 commissioning）はStep A完了後・別明示承認で
