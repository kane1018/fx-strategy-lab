# H-11 v4 Exit上限変更（23H→30M）
## 引き継ぎテンプレート（完了 / 未完了 / 根拠付き）

> **SUPERSEDED SNAPSHOT - 実行手順として使用禁止**
>
> この文書は旧G018/旧HEAD時点の調査記録であり、現在のcommissioning、
> generation作成、external preparation、actual-canaryの根拠には使用しない。
> 30分出口候補はG018を再利用せず、独立review後の新規G019として扱う。
> 現行設計は
> `docs/H11_V4_G019_RESTART_SAFE_EXIT_AND_COMMISSIONING_DESIGN.md`
> を参照する。

- 作成日: 2026-07-28
- 対象リポジトリ: `/Users/naoikansui/Desktop/トレード`
- 対象世代: G018（`H11_AUTO_30M_20260727_G018`）
- 調査時点のHEAD: `fc4d60ccbbfed29144036111cf7db428c9b8e209`
- `origin/main` と一致: `fc4d60ccbbfed29144036111cf7db428c9b8e209`

---

## 1) 完了（DONE）

### DONE-1: 23H固定から30M固定への仕様変更
- 対象: `/Users/naoikansui/Desktop/トレード/backend/app/h11_auto/v4_gmo_contracts.py`
- 変更内容:
  - `V4_GMO_EXIT_PROFILE` の名称を 30M版へ更新
    - `H11_V4_EXACT_OCO_POSITION_SPECIFIC_23H_FRIDAY_04JST_EXIT_V2`
    - `→ H11_V4_EXACT_OCO_POSITION_SPECIFIC_30M_FRIDAY_04JST_EXIT_V2`
  - `V4_GMO_MAXIMUM_HOLD_SECONDS`
    - `82_800` から `1_800` へ変更

**根拠（コマンド）**
```bash
cd /Users/naoikansui/Desktop/トレード && rg -n 'V4_GMO_MAXIMUM_HOLD_SECONDS|H11_V4_EXACT_OCO_POSITION_SPECIFIC' backend/app/h11_auto/v4_gmo_contracts.py
```

### DONE-2: 関連テストの30M方針反映
- 対象: `/Users/naoikansui/Desktop/トレード/backend/app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py`
- 変更内容:
  - 30分前提の秒数値を 82,800 系から 1,800 系へ主要更新
  - 82,801 系も 1,801 系へ更新

**根拠（コマンド）**
```bash
cd /Users/naoikansui/Desktop/トレード && rg -n '82800|82801|1800|1801' backend/app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py
```

### DONE-3: generation/evidenceの再凍結値を更新
- 対象:
  - `/Users/naoikansui/Desktop/トレード/docs/templates/h11_v4_gmo_frozen_generation.json`
  - `/Users/naoikansui/Desktop/トレード/docs/templates/h11_v4_actual_preparation_evidence.json`
- 更新内容:
  - frozen generation側に 30M exit profile と `maximum_hold_seconds: 1800` が反映
  - preparation evidence 側に、最新レビュー済み digest と generation digest を反映

**根拠（コマンド）**
```bash
cd /Users/naoikansui/Desktop/トレード && cat docs/templates/h11_v4_gmo_frozen_generation.json | head -n 40
cd /Users/naoikansui/Desktop/トレード && cat docs/templates/h11_v4_actual_preparation_evidence.json | head -n 40
cd /Users/naoikansui/Desktop/トレード && python3 - <<'PY'
from pathlib import Path
from h11_v4_reviewed_digest import compute_reviewed_files_digest
print("computed_reviewed_files_digest=", compute_reviewed_files_digest(repository=Path('..').resolve()))
PY
```

### DONE-4: 作業状態の確認
- `git status --short` により、差分は対象範囲に限定
- `git diff --check` を実行

**根拠（コマンド）**
```bash
cd /Users/naoikansui/Desktop/トレード && git status --short
cd /Users/naoikansui/Desktop/トレード && git diff --check
```

---

## 2) 未完了（NOT DONE / BLOCKING）

### NOT DONE-1: 1件テスト失敗あり（ブロッキング）
- 実行対象: `app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py`
- 失敗内容:
  - `test_v4_scheduled_time_exit_is_30m` が失敗
  - `friday_evening_entry` 期待値が `00:30 UTC` になっており、実測/仕様どおりの `11:30 UTC` と不整合

**根拠（コマンド）**
```bash
cd /Users/naoikansui/Desktop/トレード/backend && .venv/bin/python -m pytest app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py
```
- 失敗: `1 failed, 67 passed`

### NOT DONE-2: コミット/Push未完了
- 変更内容はローカルの dirty 状態のまま
  - `backend/app/h11_auto/v4_gmo_contracts.py`
  - `backend/app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py`
  - `docs/templates/h11_v4_actual_preparation_evidence.json`
  - `docs/templates/h11_v4_gmo_frozen_generation.json`
- untracked: `docs/H11_V4_EXIT_POLICY_RE1_DESIGN_20260725.md`

**根拠（コマンド）**
```bash
cd /Users/naoikansui/Desktop/トレード && git status --short
```

### NOT DONE-3: 未追跡設計ノートの取り扱い判断待ち
- `docs/H11_V4_EXIT_POLICY_RE1_DESIGN_20260725.md` は未追跡
- 本件と同一コミットに含めるか、別コミット/別管理かを事前に確定する必要あり

**根拠（コマンド）**
```bash
cd /Users/naoikansui/Desktop/トレード && git status --short
git ls-files --others -- docs/H11_V4_EXIT_POLICY_RE1_DESIGN_20260725.md
docs/H11_V4_EXIT_POLICY_RE1_DESIGN_20260725.md
```

---

## 3) 次アクション（最短）

1. `test_v4_scheduled_time_exit_is_30m` の期待値を 30分基準へ直す（最小変更）
   - `datetime(2026, 7, 17, 11, 30, tzinfo=UTC)` に修正
   - または `friday_evening_entry + timedelta(seconds=1_800)`
2. 対象テスト再実行、`68 passed` を確認
3. `tests/ruff/diff check/danger scan` ならびに独立レビュー clear を満たし、コミット/プッシュ
4. その後、G018 actual-activation準備（fresh sequence）へ進行

---

## 4) 参照先ファイル一覧
- `docs/H11_V4_G018_EXIT_30M_COMPLETION_HANDOFF.md`
- `backend/app/h11_auto/v4_gmo_contracts.py`
- `backend/app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py`
- `docs/templates/h11_v4_gmo_frozen_generation.json`
- `docs/templates/h11_v4_actual_preparation_evidence.json`
- `docs/H11_V4_EXIT_POLICY_RE1_DESIGN_20260725.md`
