# H-11 v4 Operator Commissioning Runbook（2026-08-06・G075状態）

このrunbookは、無人の自動売買完成（UIのARM ON/OFFで起動状態を変更できる仕様）へ向けた
**現在のgate状態**と**operatorが実行できる操作**・**ブロックされているgateとその解除経路**を
記録する。エージェントは実Keychain read・実Private GET・実broker POST・実通知・
LaunchAgent install・ARM実変更・実runtime state root書込を行わない（すべてoperator境界）。

canonical世代は **G075**（`H11_AUTO_30M_20260802_G075`・runtime-only corrective）である。
削除済み世代（G066〜G079のうちG075以外）を手順の前提にしないこと。

## 1. 現在のgeneration状態

HEAD・digest・テスト件数の具体値はこの文書に**書かない**。コード変更のたびに動くため、
必ず §0 のコマンドでその場の実測値を得ること（この文書は過去3回、値の陳腐化で
独立レビューの指摘を受けている）。

| generation | 役割 | status | commissioning |
|---|---|---|---|
| **G075**（canonical） | runtime-only corrective（no-POST） | `G075_RUNTIME_REVIEWED` | **未commissioning**（op60未実行） |

G075のruntime state root（`backend/market_data/h11_v4_gmo_actual_runtime/generation-<現在のgeneration digest>/`）は
**未作成**である。

### 永久HALT: 2026-08-06 に解除済み

かつてディスク上に未解決の永久HALTが2件latchされていたが、operator が §3.4 の正規手続きで
解除した。現在の未解決HALTは **0件**（`require_g075_no_unresolved_halt` は CLEAR）。

解除の記録はリネームアーカイブとして残っている（削除禁止）:

```
generation-ce098ee8…/g074-halt-discharged.20260806T234244Z.json
generation-f0e74bf0…/g075-halt-discharged.20260806T234252Z.json
```

各アーカイブは元のHALT内容を `original` に、解除記録（operator / reason /
broker_state_confirmation / halt_content_sha256）を `resolution` に保持する。
いずれの元記録も `broker_write: false` / `actual_post_count: 0` であり、
実発注は一度も発生していない（Phase Cで根絶した偽UNKNOWNの実物）。

確認コマンド:

```bash
find backend/market_data/h11_v4_gmo_actual_runtime -name "g0*-persistent-halt.json" | wc -l   # 期待 0
find backend/market_data/h11_v4_gmo_actual_runtime -name "*halt-discharged*" | wc -l          # 期待 2
```

## 2. Gate状態サマリ

| gate | 状態 | 理由 |
|---|---|---|
| テスト基盤（full suite） | **CLEAR** | §0 のコマンドで実測（0 failed であること。件数は増加が正常）。※ macOS Keychain への書き込み権限が無い実行環境では `app/tests/test_h11_v3_keychain_credential_no_post.py` の2件が error になるが、これは環境要因であり欠陥ではない |
| Ruff / diff check | **CLEAR** | — |
| 独立A/S/Oレビュー | **未CLEAR** | P0/Phase Aの変更は独立3レーンレビュー待ち |
| レビュー合格証ゲート `verify_g075_review_artifacts` | **拒否（正しい状態）** | 未レビューコードへのCLEAR移植を防ぐため。**通過させないこと** |
| digest整合（固定点） | **CLEAR** | §0 のコマンドで現在値を得ること（コード変更で動く） |
| UI契約ロード | **CLEAR** | `_load_current_contract`成功 |
| 未解決HALTスキャン `require_g075_no_unresolved_halt` | **CLEAR** | 2026-08-06 に operator が2件とも正規手続きで解除済み（§1） |
| **G075 operation 60** | **BLOCKED** | レビュー合格証ゲートが拒否するため |
| **G075 initial activation** | **BLOCKED** | 同上 |
| **UI ARM ON（G075）** | **BLOCKED** | `release_state` が `LOCKED`（initial activation 未実行・レビュー未了）。HALTが理由ではない |
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

- G075ではPOST /onは `release_state != ENABLED` により拒否（`G075_RELEASE_CAPABILITY_LOCKED`、409）。未解決HALTスキャンは現在CLEARなので拒否理由ではないが、HALTが再発すれば同経路で `G075_UNRESOLVED_HALT_PRESENT` により先に拒否される。
  POST /off は常に通る（停止操作は阻害しない）。これは**設計どおり**。
  UIが契約をロードできること（500でないこと）自体は確認済み。

### 3.3 （任意）shadow commissioning artifactの生成

```bash
backend/.venv/bin/python backend/scripts/h11_auto_v4_current_generation_shadow_commission.py
```

- 実runtime state root配下へshadow-commissioning evidenceを書く（operator実行のみ）。
- 必須ではない。

### 3.5 日次準備(00-60)が失敗したときの復旧

**まずこれを読むこと。** 11ステップのうち同日にやり直せるのは2つだけである。

| ステップ | 同日の再試行 | 理由 |
|---|---|---|
| `20_email_confirmation` | **可能** | フレーズ照合のみ。permit の下で外部作用を起こさない |
| `40_exclusivity_confirmation` | **可能** | 同上 |
| 上記以外の9ステップ | **不可** | 実外部作用(keychain 読取・通知送信・メール送信・時刻取得・kill・GET・LaunchAgent 設置)を伴う。再試行はマーカーを置換するだけで、前回の外部作用が既に発火していなかったことを証明できない |

`00_presence` は一見ローカルだが `security find-generic-password` を項目ごとに
起動するため、後者に含まれる。operator の入力を取らないので再試行は不要。

#### 20 / 40 が失敗した場合

同じコマンドを正しい値で再実行するだけでよい。古い `started` マーカーは
自動的に置換され、新しい `attempt_token` が発行される。何も削除しないこと。

なお `20_email_confirmation` はフレーズ検証を `ledger.begin()` **より前**に行うため、
打ち間違いではマーカーすら書かれない。`40_exclusivity_confirmation` は permit 取得後に
照合するため、打ち間違いは `started` マーカーを消費する — これが同日再試行を
必要とする本来の理由である。どちらの場合も、正しい値での再実行で復旧する。

#### それ以外の9ステップが失敗した場合

**その営業日の準備はそこで終わりである。** 当日はどのステップも先に進めない。

やること:

1. **何も削除しない**(マーカー・ロック・state root のいずれも)
2. 失敗の原因を調べて直す(通知設定・ネットワーク・keychain 項目など)
3. **翌営業日に `00_presence` から通しでやり直す**

翌営業日に新しいシーケンスを開始できることは設計上保証されている
(前日の未解決マーカーは当日の走査対象外)。マーカーは証拠として残す。

やってはいけないこと:

- マーカーやロックファイルの削除 — 失敗の証拠を消す行為であり、
  過去に世代量産(churn)を招いた経路そのもの
- 新しい世代の作成 — `REVIEWED_FILES` が変わり digest が動くため、
  完了済みの独立レビューが無効になる
- 同じステップの再実行を強行すること — ガードが `OPERATION_ALREADY_ATTEMPTED`
  で拒否する。拒否は正しい動作である

#### バンドラーを使っている場合の再開位置

`h11_auto_v4_daily_preparation_bundle.py` は最初の非ゼロ終了で停止する。

- **20 か 40 で止まった**(どちらもバンドラー外の手動ステップ):
  正しい値で当該コマンドを再実行し、その後 `--stage 2` または `--stage 3` へ進む
- **`--stage N` の途中で止まった**: そのステージ内の失敗ステップは当日再実行不可。
  当日の準備は終了。翌営業日に `--stage 1` から通しでやり直す
  (ステージ単位ではなく、必ず 00 から)

---

### 3.4 HALT discharge（操作者専用・renameアーカイブのみ・Phase C）

**この手続きは 2026-08-06 に実施済み**（G074/G075 の2件、§1 参照）。現在の未解決HALTは
0件なので、以下は**将来HALTが再発した場合の手順**として残している。

HALT は実害なしと operator が判断した場合も、**解除は必ずこの手続きで記録を残して行う**。
削除は禁止、rename アーカイブのみ。`--generation-digest` の値は手順 0) の列挙結果から
取ること（下の例に埋まっている値は 2026-08-06 に解除した G075 のもので、再利用しない）。

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
